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
from app.config.settings import (
    AGENT_MODE, GEMINI_API_KEY, MAX_REACT_STEPS, TOOLS_TRANSPORT,
)

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


def _propose_single(ctx: dict) -> dict:
    """ONE structured LLM call (no tool loop) — free-tier friendly default.
    Candidates are already in the prompt; the LLM weighs the trade-off and returns
    a structured proposal directly."""
    from app.agent.model import get_chat_model as _gcm  # local import keeps module light
    structured = _gcm(temperature=0.1).with_structured_output(Proposal)
    proposal: Proposal = structured.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _format_user(ctx)},
    ])
    return proposal.model_dump()


# --------------------------------------------------------------------------- #
# Public sync API (called by the runner thread)
# --------------------------------------------------------------------------- #
def propose_decision(ctx: dict) -> dict:
    if not GEMINI_API_KEY:
        return {**_heuristic_proposal(ctx), "_source": "heuristic (no GEMINI_API_KEY)"}
    try:
        if AGENT_MODE == "react":
            return {**asyncio.run(_propose_async(ctx)), "_source": f"llm-react/{TOOLS_TRANSPORT}"}
        return {**_propose_single(ctx), "_source": "llm-single"}
    except Exception as e:  # never let a model/MCP error stop the sim
        return {**_heuristic_proposal(ctx), "_source": f"heuristic (fallback: {type(e).__name__})"}


def _heuristic_proposal(ctx: dict) -> dict:
    """Transparent rule-based choice used as a fallback / before a key is set.

    Blends reliability score, price and lead time so it does not collapse onto a
    single supplier (urgency shifts the weight toward lead time)."""
    cands = ctx["candidates"]
    p = ctx["product"]
    if not cands:
        return {"chosen_supplier_id": "", "quantity": 0,
                "reasoning": "No active supplier available — escalating.", "alternatives": [],
                "confidence": 0.0, "escalate": True}

    prices = [c["unit_price"] for c in cands]
    leads = [c["lead_time_days"] for c in cands]
    pmin, pmax = min(prices), max(prices)
    lmin, lmax = min(leads), max(leads)

    def n(v, lo, hi):
        return 0.0 if hi == lo else (v - lo) / (hi - lo)

    urgent = ctx.get("urgent")
    ws, wp, wl = (0.30, 0.10, 0.60) if urgent else (0.50, 0.30, 0.20)

    def value(c):  # higher is better; cheap + fast + reliable
        return (ws * c["current_score"]
                + wp * (1 - n(c["unit_price"], pmin, pmax))
                + wl * (1 - n(c["lead_time_days"], lmin, lmax)))

    ranked = sorted(cands, key=value, reverse=True)
    chosen = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    qty = max(chosen["moq"], p["daily_usage"] * 30)
    alts = [c["supplier_id"] for c in ranked[1:4]]
    situation = "urgent (stock at or below safety stock)" if urgent else "routine reorder"
    reasoning = (
        f"{p['product_id']} ({p['name']}) hit its reorder point — stock {p['current_stock']} "
        f"vs reorder point {p['reorder_point']}; {situation}. Compared {len(cands)} active "
        f"suppliers on price, lead time and reliability. Chose {chosen['supplier_id']} "
        f"({chosen['name']}): ${chosen['unit_price']}/unit, {chosen['lead_time_days']}-day lead, "
        f"reliability {chosen['current_score']}; ordering {int(qty)} units (~30 days of usage)."
    )
    if runner:
        reasoning += (
            f" Preferred over {runner['supplier_id']} ({runner['name']}: "
            f"${runner['unit_price']}/unit, {runner['lead_time_days']}-day lead, "
            f"reliability {runner['current_score']}) because "
            + ("speed matters most here and the price gap is not worth a slower delivery that risks a stockout."
               if urgent else
               "it gives the better overall balance of price, lead time and reliability for a routine order.")
        )
    return {
        "chosen_supplier_id": chosen["supplier_id"], "quantity": int(qty),
        "reasoning": reasoning, "alternatives": alts, "confidence": 0.6, "escalate": False,
    }


# --------------------------------------------------------------------------- #
# LangGraph Studio entrypoint (langgraph.json) — static view of the ReAct graph
# --------------------------------------------------------------------------- #
def make_studio_graph():
    from langgraph.prebuilt import create_react_agent
    return create_react_agent(get_chat_model(), READ_TOOLS, prompt=SYSTEM_PROMPT)
