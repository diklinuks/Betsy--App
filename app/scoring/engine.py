"""Supplier scoring (Supplier scoring.md).

KPIs: OTD, POR, lead-time variance, price stability. Composite in [0,1].
The pure functions (normalize/composite/snapshot values) carry no DB dependency
so they are unit-testable; recompute_all_scores wires them to the database.

Normalisation note: the doc specifies a per-category rolling window. Because each
supplier carries ONE global composite score, v1 normalises each KPI across all
suppliers that have >=3 deliveries (global population). Per-category weight
overrides are still honoured via operator config.
"""
from __future__ import annotations

from statistics import median

from app.config.settings import SCORING_WINDOW

COLD_START_MIN_DELIVERIES = 3


# ----------------------------- pure helpers ----------------------------- #
def normalize(value: float, vmin: float, vmax: float, higher_is_better: bool) -> float:
    """Min-max scale to [0,1]. min==max -> 1.0 (no spread to discriminate)."""
    if vmax == vmin:
        return 1.0
    scaled = (value - vmin) / (vmax - vmin)
    return scaled if higher_is_better else 1.0 - scaled


def composite(otd_n: float, por_n: float, ltv_n: float, price_n: float, weights: dict) -> float:
    score = (
        weights["otd"] * otd_n
        + weights["por"] * por_n
        + weights["lead_time_var"] * ltv_n
        + weights["price_stability"] * price_n
    )
    return round(max(0.0, min(1.0, score)), 4)


def snapshot_values(
    *, on_time: bool, defects: int, qty_ordered: int, qty_received: int,
    expected_day: int, actual_day: int, po_unit_price: float, invoice_unit_price: float | None,
) -> dict:
    """Raw KPI values for a single delivery (stored as a KpiSnapshot row, W3)."""
    perfect = on_time and defects == 0 and qty_received >= qty_ordered
    price_dev = 0.0
    if invoice_unit_price is not None and po_unit_price:
        price_dev = abs(invoice_unit_price - po_unit_price) / po_unit_price
    return {
        "otd": 1.0 if on_time else 0.0,
        "por": 1.0 if perfect else 0.0,
        "lead_time_var": float(abs(actual_day - expected_day)),
        "price_dev": round(price_dev, 4),
    }


# ----------------------------- DB-integrated ----------------------------- #
def _aggregate(session, supplier_id: str, window: int = SCORING_WINDOW) -> dict | None:
    """Mean raw KPIs over a supplier's last `window` snapshots. None if no data."""
    from sqlalchemy import select
    from app.db.models import KpiSnapshot
    rows = session.execute(
        select(KpiSnapshot)
        .where(KpiSnapshot.supplier_id == supplier_id)
        .order_by(KpiSnapshot.id.desc())
        .limit(window)
    ).scalars().all()
    if not rows:
        return None
    n = len(rows)
    return {
        "count": n,
        "otd": sum(r.otd for r in rows) / n,
        "por": sum(r.por for r in rows) / n,
        "lead_time_var": sum(r.lead_time_var for r in rows) / n,
        "price_dev": sum(r.price_dev for r in rows) / n,
    }


def recompute_all_scores(session, weights: dict) -> dict[str, float]:
    """Recompute and persist current_score for every supplier. Returns the map."""
    from sqlalchemy import select
    from app.db.models import Supplier
    suppliers = session.execute(select(Supplier)).scalars().all()
    aggs = {s.supplier_id: _aggregate(session, s.supplier_id) for s in suppliers}

    rated = {sid: a for sid, a in aggs.items() if a and a["count"] >= COLD_START_MIN_DELIVERIES}

    scores: dict[str, float] = {}
    if rated:
        def rng(key: str) -> tuple[float, float]:
            vals = [a[key] for a in rated.values()]
            return min(vals), max(vals)

        otd_r, por_r = rng("otd"), rng("por")
        ltv_r, price_r = rng("lead_time_var"), rng("price_dev")

        for sid, a in rated.items():
            scores[sid] = composite(
                normalize(a["otd"], *otd_r, higher_is_better=True),
                normalize(a["por"], *por_r, higher_is_better=True),
                normalize(a["lead_time_var"], *ltv_r, higher_is_better=False),
                normalize(a["price_dev"], *price_r, higher_is_better=False),
                weights,
            )

    cold_start = median(scores.values()) if scores else 0.5

    for s in suppliers:
        s.current_score = scores.get(s.supplier_id, round(cold_start, 4))
    session.flush()
    return {s.supplier_id: s.current_score for s in suppliers}
