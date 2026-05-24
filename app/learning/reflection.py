"""Reflection + rejection-bank (Learning.md, Reflection frequency.md).

Outcome-triggered: a lesson is written when a PO outcome closes (delivery received
/ invoice matched) and on every Jenny rejection — NOT on every ReAct loop.
"""
from __future__ import annotations

from app.agent.model import get_reflection_model
from app.db.models import Decision
from app.learning.memory import embed_memory

_REFLECT_PROMPT = """You are Betsy's reflection step. A past procurement decision has \
now closed with a known outcome. Write ONE short lesson (max 2 sentences) that would \
help a similar future decision. Be concrete about supplier, product, and what to repeat \
or avoid.

DECISION: {reasoning}
CHOSEN: supplier {supplier} for product {product}, qty {qty}
OUTCOME: {outcome}

Lesson:"""


def reflect_on_outcome(session, decision: Decision, outcome: dict) -> str | None:
    """Write + embed a lesson after a PO outcome closes. Records outcome on the row."""
    decision.outcome = outcome
    session.flush()
    try:
        prompt = _REFLECT_PROMPT.format(
            reasoning=decision.reasoning, supplier=decision.chosen_supplier,
            product=decision.product_id, qty=decision.chosen_quantity, outcome=outcome,
        )
        lesson = get_reflection_model().invoke(prompt).content.strip()
    except Exception:
        # No model available — store a deterministic fallback lesson so learning still flows.
        verdict = "good" if outcome.get("on_time") and outcome.get("quality_pass") else "poor"
        lesson = (f"Supplier {decision.chosen_supplier} for {decision.product_id} "
                  f"produced a {verdict} outcome ({outcome}).")
    _safe_embed(session, "reflection", lesson, decision)
    return lesson


def record_rejection(session, decision: Decision, jenny_reason: str) -> str:
    """Store Jenny's rejection as a few-shot lesson (rejection bank)."""
    lesson = (f"Jenny REJECTED choosing supplier {decision.chosen_supplier} for "
              f"product {decision.product_id}. Reason: {jenny_reason}. "
              f"Avoid this choice in similar cases.")
    _safe_embed(session, "rejection", lesson, decision)
    return lesson


def _safe_embed(session, kind: str, text: str, decision) -> None:
    """Embed best-effort; an embedding/model error must never crash the sim."""
    try:
        embed_memory(session, kind=kind, text=text, decision_id=decision.decision_id,
                     supplier_id=decision.chosen_supplier, product_id=decision.product_id,
                     created_day=decision.sim_day)
    except Exception as e:  # noqa: BLE001
        print(f"[learning] embed skipped ({type(e).__name__}): {e}")
