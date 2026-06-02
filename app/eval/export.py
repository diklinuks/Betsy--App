"""Static replay export — record a full 90-day run into ONE JSON bundle.

`python -m app.main export [out.json]` resets the DB, loads the dataset, runs the
sim headless (auto-approving escalations for a clean scorecard), snapshots per-day
state through the runner's `on_day_end` hook, then serialises everything the replay
UI needs into a single file. Works WITHOUT a Gemini key (heuristic fallback), so the
artifact is reproducible offline and safe to commit + serve from GitHub Pages.

The bundle shape (consumed by web/ui):
    meta       — run metadata + caps + weights
    suppliers  — final state + per-day score history
    products   — final state + per-day stock history
    days[]     — per-day snapshot: summary, inventory, supplier scores/status, spend
    events[]   — flat, ordered activity stream (the heart of the replay)
    decisions  — full audit log (candidates, reasoning, outcome, attribution)
    approvals  — escalations + how they resolved
    deliveries / invoices / lessons / scenarios / report
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.config.settings import AGENT_MODE, GEMINI_API_KEY, SIM_DAYS
from app.db.config_repo import current_config
from app.db.models import (
    Decision, Delivery, Event, Invoice, PendingApproval, Product, PurchaseOrder, Supplier,
)
from app.db.session import get_session
from app.eval.report import build_report
from app.sim import runner
from app.sim.scenarios import SCENARIOS
from app.tools.functions import _month_to_date_spend
from app.util import day_to_date, sim_day as to_sim_day

DEFAULT_OUT = Path("web/ui/public/run.json")


# ----------------------------- serialisers ----------------------------- #
def _scenario_description(sc: dict) -> str:
    t = sc["type"]
    if t == "demand_spike":
        return f"Demand spike on {sc['product']}: +{sc['extra']} units/day"
    if t == "force_stockout":
        return f"Forced stockout on {sc['product']}"
    if t == "bankruptcy":
        return f"Supplier {sc['supplier']} goes bankrupt — open POs cancelled"
    if t == "supplier_shortage":
        return f"Supplier {sc['supplier']} in shortage (days {sc['sim_day']}–{sc.get('until_sim_day')})"
    if t == "late_delivery":
        return f"Late delivery (+{sc['delay_days']}d) on the next arrival after day {sc['sim_day']}"
    if t == "wrong_quantity":
        return f"Short shipment (−{sc['short']} units)"
    if t == "defect":
        return f"Defective batch ({sc['defect_units']} units)"
    if t == "partial_delivery":
        return (f"Partial delivery ({int(sc['first_fraction']*100)}% first, "
                f"remainder +{sc['remainder_delay']}d)")
    if t == "invoice_mismatch":
        return f"Inflated invoice (+{int(sc['extra_pct']*100)}%)"
    if t == "duplicate_invoice":
        return "Duplicate invoice submitted"
    return t.replace("_", " ")


def _cumulative_spend(s, abs_day: int) -> float:
    d = day_to_date(abs_day)
    total = s.execute(
        select(func.coalesce(func.sum(PurchaseOrder.total_amount), 0.0)).where(
            PurchaseOrder.placed_date <= d,
            PurchaseOrder.status.notin_(["cancelled", "rejected"]))
    ).scalar_one()
    return float(total)


def _event_dict(e: Event) -> dict:
    return {
        "id": e.id, "sim_day": e.sim_day, "abs_day": e.abs_day, "kind": e.kind,
        "severity": e.severity, "title": e.title, "detail": e.detail or {},
        "product_id": e.product_id, "supplier_id": e.supplier_id,
        "po_id": e.po_id, "decision_id": e.decision_id,
    }


def _decision_dict(d: Decision) -> dict:
    return {
        "decision_id": d.decision_id, "sim_day": d.sim_day, "trigger_type": d.trigger_type,
        "product_id": d.product_id, "candidates": d.candidates or [],
        "chosen_supplier": d.chosen_supplier, "chosen_quantity": d.chosen_quantity,
        "reasoning": d.reasoning, "alternatives": d.alternatives or [],
        "confidence": d.confidence, "action": d.action, "escalated": d.escalated,
        "urgent": d.urgent, "attribution": d.attribution, "config_version": d.config_version,
        "outcome": d.outcome,
    }


def _delivery_dict(d: Delivery) -> dict:
    return {
        "delivery_id": d.delivery_id, "po_id": d.po_id, "supplier_id": d.supplier_id,
        "product_id": d.product_id, "sim_day": to_sim_day(d.actual_delivery_day),
        "expected_sim_day": to_sim_day(d.expected_delivery_day),
        "quantity_ordered": d.quantity_ordered, "quantity_received": d.quantity_received,
        "on_time": d.on_time, "quality_pass": d.quality_pass, "defects_count": d.defects_count,
        "notes": d.notes,
    }


def _invoice_dict(v: Invoice) -> dict:
    return {
        "invoice_id": v.invoice_id, "invoice_number": v.invoice_number, "po_id": v.po_id,
        "supplier_id": v.supplier_id, "sim_day": to_sim_day(v.invoice_day),
        "amount": round(v.amount, 2), "po_amount": round(v.po_amount, 2),
        "matches_po": v.matches_po, "is_duplicate": v.is_duplicate,
        "payment_status": v.payment_status, "anomaly_flag": v.anomaly_flag,
    }


# ----------------------------- the export ----------------------------- #
def export_run(out_path: str | Path = DEFAULT_OUT) -> dict:
    """Reset → load → run → serialise. Returns the bundle (also written to disk)."""
    from app.db.loader import load_all

    print("Loading dataset (reset)…")
    load_all(reset=True)

    day_snaps: list[dict] = []

    def on_day_end(abs_day: int) -> None:
        with get_session() as s:
            prods = s.execute(select(Product)).scalars().all()
            sups = s.execute(select(Supplier)).scalars().all()
            _, cfg = current_config(s)
            inv = [{
                "product_id": p.product_id, "stock": p.current_stock,
                "reorder_point": p.reorder_point, "safety_stock": p.safety_stock,
                "daily_usage": p.daily_usage_rate,
                "days_cover": round(p.current_stock / p.daily_usage_rate, 1) if p.daily_usage_rate else None,
                "below_reorder": p.current_stock <= p.reorder_point,
            } for p in prods]
            day_snaps.append({
                "sim_day": to_sim_day(abs_day), "abs_day": abs_day,
                "date": day_to_date(abs_day).isoformat(),
                "inventory": inv,
                "supplier_scores": {sup.supplier_id: round(sup.current_score, 4) for sup in sups},
                "supplier_status": {sup.supplier_id: sup.status for sup in sups},
                "spend_to_date": round(_cumulative_spend(s, abs_day), 2),
                "spend_mtd": round(_month_to_date_spend(s, abs_day), 2),
                "monthly_cap": cfg.get("monthly_cap"),
            })

    print(f"Running {SIM_DAYS}-day simulation headless…")
    runner.AUTO_APPROVE = True
    runner._run(on_day_end=on_day_end)

    # ------- serialise everything from the DB -------
    with get_session() as s:
        _, cfg = current_config(s)
        suppliers = s.execute(select(Supplier).order_by(Supplier.supplier_id)).scalars().all()
        products = s.execute(select(Product).order_by(Product.product_id)).scalars().all()
        events = s.execute(select(Event).order_by(Event.id)).scalars().all()
        decisions = s.execute(select(Decision).order_by(Decision.sim_day, Decision.created_at)).scalars().all()
        approvals = s.execute(select(PendingApproval).order_by(PendingApproval.sim_day)).scalars().all()
        deliveries = s.execute(
            select(Delivery).where(Delivery.phase == "simulation")
            .order_by(Delivery.actual_delivery_day)).scalars().all()
        invoices = s.execute(
            select(Invoice).where(Invoice.phase == "simulation")
            .order_by(Invoice.invoice_day)).scalars().all()

        event_dicts = [_event_dict(e) for e in events]

        # per-entity histories (cheap; sparklines)
        score_hist = {sup.supplier_id: [] for sup in suppliers}
        stock_hist = {p.product_id: [] for p in products}
        for snap in day_snaps:
            for sid, sc in snap["supplier_scores"].items():
                score_hist.setdefault(sid, []).append({"sim_day": snap["sim_day"], "score": sc})
            for row in snap["inventory"]:
                stock_hist.setdefault(row["product_id"], []).append(
                    {"sim_day": snap["sim_day"], "stock": row["stock"]})

        supplier_list = [{
            "supplier_id": sup.supplier_id, "name": sup.name, "price_tier": sup.price_tier,
            "base_lead_time_days": sup.base_lead_time_days, "payment_terms": sup.payment_terms,
            "category_focus": sup.category_focus, "final_score": round(sup.current_score, 4),
            "status": sup.status, "score_history": score_hist.get(sup.supplier_id, []),
        } for sup in suppliers]

        product_list = [{
            "product_id": p.product_id, "name": p.name, "category": p.category,
            "abc_class": p.abc_class, "unit": p.unit, "daily_usage": p.daily_usage_rate,
            "reorder_point": p.reorder_point, "safety_stock": p.safety_stock,
            "base_unit_price": p.base_unit_price, "stock_history": stock_hist.get(p.product_id, []),
        } for p in products]

        lessons = [{
            "sim_day": e["sim_day"], "supplier_id": e["supplier_id"],
            "product_id": e["product_id"], "decision_id": e["decision_id"],
            "kind": (e["detail"] or {}).get("kind", "reflection"),
            "text": (e["detail"] or {}).get("lesson", e["title"]),
        } for e in event_dicts if e["kind"] == "lesson"]

    # scenario coverage comes from the report (SimState.fired_scenarios)
    report = build_report()
    fired_ids = set(report.get("scenario_coverage", {}).get("fired", []))
    scenarios = [{
        "id": sc["id"], "type": sc["type"], "trigger_sim_day": sc.get("sim_day"),
        "description": _scenario_description(sc), "fired": sc["id"] in fired_ids,
    } for sc in SCENARIOS]

    bundle = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sim_days": SIM_DAYS, "start_date": day_to_date(61).isoformat(), "seed": 42,
            "agent_mode": AGENT_MODE, "used_llm": bool(GEMINI_API_KEY),
            "per_po_cap": cfg.get("per_po_cap"), "monthly_cap": cfg.get("monthly_cap"),
            "weights": cfg.get("weights", {}),
            "counts": {
                "events": len(event_dicts), "decisions": len(decisions),
                "deliveries": len(deliveries), "invoices": len(invoices),
                "approvals": len(approvals), "lessons": len(lessons),
            },
        },
        "suppliers": supplier_list,
        "products": product_list,
        "days": day_snaps,
        "events": event_dicts,
        "decisions": [_decision_dict(d) for d in decisions],
        "approvals": [{
            "decision_id": a.decision_id, "sim_day": a.sim_day, "product_id": a.product_id,
            "proposal": a.proposal, "reason_needed": a.reason_needed, "status": a.status,
            "jenny_reason": a.jenny_reason,
        } for a in approvals],
        "deliveries": [_delivery_dict(d) for d in deliveries],
        "invoices": [_invoice_dict(v) for v in invoices],
        "lessons": lessons,
        "scenarios": scenarios,
        "report": report,
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, indent=2, default=str))
    c = bundle["meta"]["counts"]
    print(f"\n✓ Wrote {out} — {len(day_snaps)} days, {c['events']} events, "
          f"{c['decisions']} decisions, {c['deliveries']} deliveries, "
          f"{c['invoices']} invoices, {c['lessons']} lessons.")
    print(f"  Report: stockouts prevented={report['stockouts']['prevented']}, "
          f"invoice errors caught={report['invoice_errors_caught']}, "
          f"approval rate={report['approvals']['rate']}, "
          f"scenarios fired={len(fired_ids)}/{len(SCENARIOS)}")
    return bundle
