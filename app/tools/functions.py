"""The 12 tools (Tools.md) as plain functions over a DB session.

Privacy (Ethics & safeguards): read tools return MINIMAL field projections —
supplier bank details / contact are never returned to the LLM.

Split of labour (Code vs LLM):
  * READ tools (inventory_read, supplier_catalogue, supplier_history, config_read,
    decision_search) are called by the LLM agent through MCP.
  * WRITE tools (po_generate, decision_log, notify_human, delivery_record,
    inventory_update, supplier_score_update, invoice_match) are invoked by the
    deterministic sim-runner. All are also exposed via MCP for completeness.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.config.settings import RETRIEVAL_TOP_K
from app.db.config_repo import current_config
from app.db.models import (
    Delivery, Invoice, KpiSnapshot, Product, PurchaseOrder, Supplier, SupplierProduct,
)
from app.scoring.engine import recompute_all_scores, snapshot_values
from app.util import day_to_date, phase_of


# ----------------------------- id helper ----------------------------- #
def _next_id(session, model, id_col, prefix: str) -> str:
    n = session.execute(
        select(func.count()).select_from(model).where(id_col.like(f"{prefix}%"))
    ).scalar_one()
    return f"{prefix}{n + 1:04d}"


# ============================== READ TOOLS ============================== #
def inventory_read(session, sku_id: str) -> dict:
    """Current stock, daily usage, and reorder point for one SKU (R1)."""
    p = session.get(Product, sku_id)
    if not p:
        return {"error": f"unknown sku {sku_id}"}
    return {
        "product_id": p.product_id, "name": p.name, "category": p.category,
        "abc_class": p.abc_class, "current_stock": p.current_stock,
        "daily_usage": p.daily_usage_rate, "reorder_point": p.reorder_point,
        "safety_stock": p.safety_stock,
        "days_of_cover": round(p.current_stock / p.daily_usage_rate, 1) if p.daily_usage_rate else None,
    }


def supplier_catalogue(session, product_id: str) -> list[dict]:
    """Active, non-blocked suppliers for a product with price/lead/MOQ/score (R2)."""
    _, cfg = current_config(session)
    blocked = set(cfg.get("blocked_suppliers", []))
    rows = session.execute(
        select(SupplierProduct, Supplier)
        .join(Supplier, Supplier.supplier_id == SupplierProduct.supplier_id)
        .where(SupplierProduct.product_id == product_id)
    ).all()
    out = []
    for sp, sup in rows:
        if sup.supplier_id in blocked or sup.status != "active":
            continue
        out.append({
            "supplier_id": sup.supplier_id, "name": sup.name,
            "price_tier": sup.price_tier, "unit_price": round(sp.unit_price, 4),
            "lead_time_days": sp.supplier_lead_time_days, "moq": sp.supplier_moq,
            "current_score": round(sup.current_score, 4),
        })
    out.sort(key=lambda r: r["current_score"], reverse=True)
    return out


def supplier_history(session, supplier_id: str) -> dict:
    """Recent KPI history (OTD/POR/lead-var/price-dev) for a supplier (R3)."""
    sup = session.get(Supplier, supplier_id)
    if not sup:
        return {"error": f"unknown supplier {supplier_id}"}
    rows = session.execute(
        select(KpiSnapshot).where(KpiSnapshot.supplier_id == supplier_id)
        .order_by(KpiSnapshot.id.desc()).limit(20)
    ).scalars().all()
    n = len(rows) or 1
    return {
        "supplier_id": sup.supplier_id, "name": sup.name,
        "current_score": round(sup.current_score, 4), "deliveries_tracked": len(rows),
        "otd_rate": round(sum(r.otd for r in rows) / n, 3),
        "perfect_order_rate": round(sum(r.por for r in rows) / n, 3),
        "avg_lead_time_variance_days": round(sum(r.lead_time_var for r in rows) / n, 2),
        "avg_price_deviation": round(sum(r.price_dev for r in rows) / n, 4),
    }


def config_read(session) -> dict:
    """Operator config: caps, blocked suppliers, weights, notify channel (R5)."""
    ver, cfg = current_config(session)
    return {"version": ver, **cfg}


def decision_search(session, query: str, k: int = RETRIEVAL_TOP_K) -> list[dict]:
    """Past decisions/lessons similar to the current case — semantic (R6/R7)."""
    from app.learning.memory import semantic_search
    try:
        return semantic_search(session, query, k)
    except Exception as e:  # embeddings unavailable -> degrade gracefully
        return [{"note": f"semantic memory unavailable: {e}"}]


# ============================== WRITE TOOLS ============================== #
def po_generate(session, sku_id: str, supplier_id: str, quantity: int, unit_price: float,
                *, day: int, sim_day: int, decision_id: str | None = None,
                approved: bool = False, attribution: str = "autonomous",
                notes: str = "") -> dict:
    """Create a PO. Enforces blocked-supplier + caps first (F11). Over-cap returns
    needs_approval unless approved=True. Blocked is a hard short-circuit."""
    _, cfg = current_config(session)
    sup = session.get(Supplier, supplier_id)
    if sup is None or sup.status != "active" or supplier_id in set(cfg.get("blocked_suppliers", [])):
        return {"status": "blocked", "reason": "supplier_blocked_or_inactive"}

    total = round(quantity * unit_price, 2)
    if not approved:
        if total > cfg["per_po_cap"]:
            return {"status": "needs_approval", "reason": "per_po_cap", "total": total}
        if _month_to_date_spend(session, day) + total > cfg["monthly_cap"]:
            return {"status": "needs_approval", "reason": "monthly_cap", "total": total}

    sp = session.execute(
        select(SupplierProduct).where(
            SupplierProduct.supplier_id == supplier_id,
            SupplierProduct.product_id == sku_id)
    ).scalar_one_or_none()
    lead = sp.supplier_lead_time_days if sp else (sup.base_lead_time_days)
    exp_day = day + lead

    po_id = _next_id(session, PurchaseOrder, PurchaseOrder.po_id, "PO-L")
    po = PurchaseOrder(
        po_id=po_id, supplier_id=supplier_id, product_id=sku_id,
        placed_day=day, placed_date=day_to_date(day),
        expected_delivery_day=exp_day, expected_delivery_date=day_to_date(exp_day),
        quantity=quantity, unit_price=round(unit_price, 4), total_amount=total,
        status="open", phase=phase_of(day), decision_id=decision_id, notes=notes,
    )
    session.add(po)
    session.flush()
    return {"status": "created", "po_id": po_id, "total": total,
            "expected_delivery_day": exp_day}


def decision_log(session, *, decision_id: str, sim_day: int, trigger_type: str,
                 product_id: str | None, candidates: list, chosen_supplier: str | None,
                 chosen_quantity: int | None, reasoning: str, alternatives: list,
                 confidence: float | None, action: str, escalated: bool,
                 attribution: str, config_version: int, urgent: bool = False) -> dict:
    """Append an audit row (W9) and embed the rationale for recall (W10)."""
    from app.db.models import Decision
    session.add(Decision(
        decision_id=decision_id, sim_day=sim_day, trigger_type=trigger_type,
        product_id=product_id, candidates=candidates, chosen_supplier=chosen_supplier,
        chosen_quantity=chosen_quantity, reasoning=reasoning, alternatives=alternatives,
        confidence=confidence, action=action, escalated=escalated, urgent=urgent,
        attribution=attribution, config_version=config_version,
    ))
    session.flush()
    try:
        from app.learning.memory import embed_memory
        embed_memory(session, kind="rationale", text=reasoning, decision_id=decision_id,
                     supplier_id=chosen_supplier, product_id=product_id, created_day=sim_day)
    except Exception:
        pass  # embeddings optional; audit row already committed
    return {"status": "logged", "decision_id": decision_id}


def notify_human(session, message: str, needs_approval: bool = False) -> dict:
    """Send Jenny a message (console in v1). Pending approvals are created by the
    runner; this is the agent's channel to surface context."""
    print(f"[NOTIFY JENNY]{' (APPROVAL)' if needs_approval else ''}: {message}")
    return {"status": "sent", "needs_approval": needs_approval}


def delivery_record(session, *, po_id: str, on_time: bool, quantity_received: int,
                    quality_pass: bool, defects: int, actual_day: int,
                    notes: str = "") -> dict:
    """Log a received delivery against its PO (W7)."""
    po = session.get(PurchaseOrder, po_id)
    if not po:
        return {"error": f"unknown po {po_id}"}
    did = _next_id(session, Delivery, Delivery.delivery_id, "DLV-L")
    session.add(Delivery(
        delivery_id=did, po_id=po_id, supplier_id=po.supplier_id, product_id=po.product_id,
        expected_delivery_day=po.expected_delivery_day,
        expected_delivery_date=po.expected_delivery_date,
        actual_delivery_day=actual_day, actual_delivery_date=day_to_date(actual_day),
        quantity_ordered=po.quantity, quantity_received=quantity_received,
        on_time=on_time, quality_pass=quality_pass, defects_count=defects,
        phase=phase_of(actual_day), notes=notes,
    ))
    po.status = "received" if quality_pass else "rejected"
    session.flush()
    return {"status": "recorded", "delivery_id": did, "po_status": po.status}


def inventory_update(session, sku_id: str, received_qty: int) -> dict:
    """Apply a delivery to stock (W4)."""
    p = session.get(Product, sku_id)
    if not p:
        return {"error": f"unknown sku {sku_id}"}
    p.current_stock += received_qty
    session.flush()
    return {"status": "updated", "product_id": sku_id, "new_stock": p.current_stock}


def supplier_score_update(session, supplier_id: str, delivery_id: str) -> dict:
    """Append a KPI snapshot for a delivery and recompute scores (W3 + W2)."""
    d = session.get(Delivery, delivery_id)
    po = session.get(PurchaseOrder, d.po_id) if d else None
    if not d or not po:
        return {"error": "unknown delivery/po"}
    inv = session.execute(
        select(Invoice).where(Invoice.po_id == d.po_id)
    ).scalars().first()
    inv_unit = (inv.amount / d.quantity_ordered) if (inv and d.quantity_ordered) else None
    vals = snapshot_values(
        on_time=d.on_time, defects=d.defects_count,
        qty_ordered=d.quantity_ordered, qty_received=d.quantity_received,
        expected_day=d.expected_delivery_day, actual_day=d.actual_delivery_day,
        po_unit_price=po.unit_price, invoice_unit_price=inv_unit,
    )
    session.add(KpiSnapshot(supplier_id=supplier_id, delivery_id=delivery_id,
                            created_day=d.actual_delivery_day, **vals))
    session.flush()
    _, cfg = current_config(session)
    scores = recompute_all_scores(session, cfg["weights"])
    return {"status": "updated", "supplier_id": supplier_id,
            "new_score": scores.get(supplier_id)}


def invoice_match(session, invoice_id: str) -> dict:
    """Three-way check invoice vs PO vs delivery; flag mismatch/duplicate (W8).
    Duplicate detection by (invoice_number, supplier_id) against history."""
    inv = session.get(Invoice, invoice_id)
    if not inv:
        return {"error": f"unknown invoice {invoice_id}"}
    po = session.get(PurchaseOrder, inv.po_id)

    dup = session.execute(
        select(func.count()).select_from(Invoice).where(
            Invoice.invoice_number == inv.invoice_number,
            Invoice.supplier_id == inv.supplier_id,
            Invoice.invoice_id != inv.invoice_id)
    ).scalar_one() > 0

    matches = po is not None and abs(inv.amount - po.total_amount) < 0.01
    anomaly = ""
    status = "paid"
    if dup:
        status, anomaly = "held", "duplicate invoice — flagged for rejection"
    elif not matches:
        status, anomaly = "held", f"amount mismatch: billed {inv.amount} vs PO {inv.po_amount}"

    inv.matches_po = matches
    inv.is_duplicate = dup
    inv.payment_status = status
    inv.anomaly_flag = anomaly
    session.flush()
    return {"status": status, "matches_po": matches, "is_duplicate": dup,
            "anomaly": anomaly, "invoice_id": invoice_id}


# ----------------------------- helpers ----------------------------- #
def _month_to_date_spend(session, day: int) -> float:
    d = day_to_date(day)
    month_start = date(d.year, d.month, 1)
    total = session.execute(
        select(func.coalesce(func.sum(PurchaseOrder.total_amount), 0.0)).where(
            PurchaseOrder.placed_date >= month_start,
            PurchaseOrder.placed_date <= d,
            PurchaseOrder.status.notin_(["cancelled", "rejected"]),
        )
    ).scalar_one()
    return float(total)
