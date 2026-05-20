"""Betsy's reasoning: a ReAct agent (LangGraph) over the MCP read tools that returns
a structured Proposal. The deterministic write/approval flow lives in app/sim/runner.py
(Code vs LLM: the LLM proposes; code decides, enforces caps, and writes).

If Gemini or MCP is unavailable, propose_decision falls back to a transparent
heuristic so the simulation still completes — the LLM upgrades the quality once
GEMINI_API_KEY is set.
"""
from __future__ import annotations

import asyncio
import sys

from app.agent.model import get_chat_model
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.schemas import Proposal
from app.agent.tools_lc import READ_TOOLS
from app.config.settings import GEMINI_API_KEY, MAX_REACT_STEPS, TOOLS_TRANSPORT

_READ_TOOL_NAMES = {
    "inventory_read", "supplier_catalogue", "supplier_history",
    "config_read", "decision_search",
}


# --------------------------------------------------------------------------- #
# Tool loading (MCP default, local fallback)
# --------------------------------------------------------------------------- #
async def _load_tools():
    if TOOLS_TRANSPORT == "local":
        return READ_TOOLS
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient({
        "betsy": {
            "command": sys.executable,
            "args": ["-m", "app.mcp_server.server"],
            "transport": "stdio",
        }
    })
    tools = await client.get_tools()
    return [t for t in tools if t.name in _READ_TOOL_NAMES]


# --------------------------------------------------------------------------- #
# LLM path
# --------------------------------------------------------------------------- #
def _format_user(ctx: dict) -> str:
    p = ctx["product"]
    lines = [
        f"SKU {p['product_id']} ({p['name']}, ABC class {p['abc_class']}) hit its reorder point.",
        f"Stock: {p['current_stock']} | reorder point: {p['reorder_point']} | "
        f"safety stock: {p['safety_stock']} | daily usage: {p['daily_usage']}.",
        "URGENT (at/below safety stock)." if ctx.get("urgent") else "Normal reorder.",
        "",
        "Candidate suppliers (also available via supplier_catalogue):",
    ]
    for c in ctx["candidates"]:
        lines.append(
            f"  - {c['supplier_id']} {c['name']}: ${c['unit_price']}/unit, "
            f"lead {c['lead_time_days']}d, MOQ {c['moq']}, score {c['current_score']}"
        )
    lines.append("\nUse supplier_history and decision_search before deciding. "
                 "Then give your structured proposal.")
    return "\n".join(lines)


async def _propose_async(ctx: dict) -> dict:
    from langgraph.prebuilt import create_react_agent

    tools = await _load_tools()
    agent = create_react_agent(get_chat_model(), tools, prompt=SYSTEM_PROMPT)
    user = _format_user(ctx)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user}]},
        config={"recursion_limit": MAX_REACT_STEPS * 2},
    )
    reasoning_trace = result["messages"][-1].content

    structured = get_chat_model(temperature=0.0).with_structured_output(Proposal)
    proposal: Proposal = await structured.ainvoke([
        {"role": "system", "content": "Extract Betsy's final procurement proposal as structured data."},
        {"role": "user", "content": user + "\n\nBetsy's reasoning:\n" + reasoning_trace},
    ])
    return proposal.model_dump()


# --------------------------------------------------------------------------- #
# Public sync API (called by the runner thread)
# --------------------------------------------------------------------------- #
def propose_decision(ctx: dict) -> dict:
    if not GEMINI_API_KEY:
        return {**_heuristic_proposal(ctx), "_source": "heuristic (no GEMINI_API_KEY)"}
    try:
        return {**asyncio.run(_propose_async(ctx)), "_source": TOOLS_TRANSPORT}
    except Exception as e:  # never let a model/MCP error stop the sim
        return {**_heuristic_proposal(ctx), "_source": f"heuristic (fallback: {type(e).__name__})"}


def _heuristic_proposal(ctx: dict) -> dict:
    """Transparent rule-based choice used as a fallback / before a key is set."""
    cands = ctx["candidates"]
    p = ctx["product"]
    if not cands:
        return {"chosen_supplier_id": "", "quantity": 0,
                "reasoning": "No active supplier available.", "alternatives": [],
                "confidence": 0.0, "escalate": True}
    if ctx.get("urgent"):
        chosen = min(cands, key=lambda c: (c["lead_time_days"], -c["current_score"]))
        why = "urgent: fastest supplier to avoid stockout"
    else:
        chosen = max(cands, key=lambda c: (c["current_score"], -c["unit_price"]))
        why = "best reliability score within normal cost"
    qty = max(chosen["moq"], p["daily_usage"] * 30)
    alts = [c["supplier_id"] for c in cands if c["supplier_id"] != chosen["supplier_id"]][:3]
    return {
        "chosen_supplier_id": chosen["supplier_id"], "quantity": int(qty),
        "reasoning": f"Chose {chosen['supplier_id']} — {why} "
                     f"(${chosen['unit_price']}/unit, lead {chosen['lead_time_days']}d, "
                     f"score {chosen['current_score']}).",
        "alternatives": alts, "confidence": 0.6, "escalate": False,
    }


# --------------------------------------------------------------------------- #
# LangGraph Studio entrypoint (langgraph.json) — static view of the ReAct graph
# --------------------------------------------------------------------------- #
def make_studio_graph():
    from langgraph.prebuilt import create_react_agent
    return create_react_agent(get_chat_model(), READ_TOOLS, prompt=SYSTEM_PROMPT)
