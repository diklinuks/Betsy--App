"""End-of-run scorecard vs the Project Description success criteria:
  * prevent >= 2 stockouts
  * catch >= 1 invoice error
  * maintain 95%+ human approval rate
plus scenario coverage and supplier-score movement.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import Decision, Invoice, PendingApproval, SimState, Supplier
from app.db.session import get_session
from app.sim.scenarios import SCENARIOS


def _empty_report(msg: str = "No simulation data yet — load and run first.") -> dict:
    z = {"target": 0, "actual": 0, "pass": False}
    return {
        "note": msg, "all_criteria_pass": False,
        "success_criteria": {"prevent_2_stockouts": {"target": 2, "actual": 0, "pass": False},
                             "catch_1_invoice_error": {"target": 1, "actual": 0, "pass": False},
                             "approval_rate_95pct": {"target": 0.95, "actual": 0, "pass": False}},
        "approvals": {"approved": 0, "rejected": 0, "rate": 0},
        "invoice_errors_caught": 0,
        "stockouts": {"occurred": 0, "prevented": 0},
        "decisions": {"total": 0, "pos_generated": 0, "escalated": 0},
        "scenario_coverage": {"fired": [], "missing": [], "detail": {}},
        "final_supplier_scores": {},
    }


def build_report() -> dict:
    try:
        return _compute_report()
    except Exception as e:  # never let the report page crash
        return _empty_report(f"Report unavailable: {type(e).__name__}: {e}")


def _compute_report() -> dict:
    with get_session() as s:
        # --- approvals ---
        approved = s.execute(select(func.count()).select_from(PendingApproval)
                             .where(PendingApproval.status == "approved")).scalar_one()
        rejected = s.execute(select(func.count()).select_from(PendingApproval)
                             .where(PendingApproval.status == "rejected")).scalar_one()
        resolved = approved + rejected
        approval_rate = (approved / resolved) if resolved else 1.0

        # --- invoices ---
        invoice_errors = s.execute(select(func.count()).select_from(Invoice)
                                   .where(Invoice.payment_status == "held",
                                          Invoice.phase == "simulation")).scalar_one()

        # --- stockouts ---
        # "Prevented" = SKUs Betsy replenished (a reorder PO was placed) that never
        # recorded an actual stockout. This credits reordering BEFORE stock hits zero,
        # which is exactly the good behaviour (the old metric only counted late saves).
        replenished = set(s.execute(
            select(Decision.product_id).where(
                Decision.trigger_type == "reorder", Decision.action == "po_generated",
                Decision.product_id.isnot(None))).scalars().all())
        stockout_products = set(s.execute(
            select(Decision.product_id).where(
                Decision.trigger_type == "stockout", Decision.product_id.isnot(None))).scalars().all())
        stockouts_occurred = len(stockout_products)
        stockouts_prevented = len(replenished - stockout_products)

        # --- decision volume ---
        total_decisions = s.execute(select(func.count()).select_from(Decision)).scalar_one()
        pos_generated = s.execute(select(func.count()).select_from(Decision)
                                  .where(Decision.action == "po_generated")).scalar_one()
        escalated = s.execute(select(func.count()).select_from(Decision)
                              .where(Decision.escalated.is_(True))).scalar_one()

        # --- scenario coverage ---
        st = s.get(SimState, 1)
        fired = set(st.fired_scenarios or []) if st else set()
        all_ids = [sc["id"] for sc in SCENARIOS]
        coverage = {sid: (sid in fired) for sid in all_ids}

        # --- supplier scores ---
        scores = {sup.supplier_id: round(sup.current_score, 3)
                  for sup in s.execute(select(Supplier)).scalars()}

    criteria = {
        "prevent_2_stockouts": {"target": 2, "actual": stockouts_prevented,
                                "pass": stockouts_prevented >= 2},
        "catch_1_invoice_error": {"target": 1, "actual": invoice_errors,
                                  "pass": invoice_errors >= 1},
        "approval_rate_95pct": {"target": 0.95, "actual": round(approval_rate, 3),
                                "pass": approval_rate >= 0.95},
    }
    return {
        "success_criteria": criteria,
        "all_criteria_pass": all(c["pass"] for c in criteria.values()),
        "approvals": {"approved": approved, "rejected": rejected,
                      "rate": round(approval_rate, 3)},
        "invoice_errors_caught": invoice_errors,
        "stockouts": {"occurred": stockouts_occurred, "prevented": stockouts_prevented},
        "decisions": {"total": total_decisions, "pos_generated": pos_generated,
                      "escalated": escalated},
        "scenario_coverage": {"fired": sorted(fired), "missing": [i for i in all_ids if i not in fired],
                              "detail": coverage},
        "final_supplier_scores": dict(sorted(scores.items())),
    }


def print_report() -> dict:
    import json
    rep = build_report()
    print(json.dumps(rep, indent=2))
    return rep


if __name__ == "__main__":
    print_report()
