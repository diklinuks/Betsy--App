"""Structured event emission — the traceability backbone.

`emit()` appends one row to the `events` table. The runner and world call it at
every meaningful step so the process Betsy goes through (consume → reorder →
propose → place PO → receive delivery → reconcile invoice → learn) is fully
visible in the live Activity feed and in the static replay export.

Kept deliberately tiny and crash-proof: a logging failure must never stop the sim.
"""
from __future__ import annotations

from app.db.models import Event
from app.util import sim_day as to_sim_day

# Severity vocabulary (drives colour in the UI):
#   info   — routine step                       good — clean/positive outcome
#   action — Betsy took an autonomous action     warn — needs attention / escalated
#   bad    — problem / anomaly / failure
SEVERITIES = {"info", "good", "action", "warn", "bad"}


def emit(session, *, abs_day: int, kind: str, title: str, severity: str = "info",
         detail: dict | None = None, product_id: str | None = None,
         supplier_id: str | None = None, po_id: str | None = None,
         decision_id: str | None = None) -> None:
    """Append one event row. Never raises (traceability is best-effort)."""
    try:
        session.add(Event(
            abs_day=abs_day, sim_day=to_sim_day(abs_day), kind=kind,
            severity=severity if severity in SEVERITIES else "info",
            title=title, detail=detail or {}, product_id=product_id,
            supplier_id=supplier_id, po_id=po_id, decision_id=decision_id,
        ))
        session.flush()
    except Exception as e:  # noqa: BLE001 — logging must not break the run
        print(f"[events] emit skipped ({type(e).__name__}): {e}")
