"""Load the synthetic dataset into Postgres and seed initial state.

Per the world-simulator decision, only static catalogs + HISTORICAL-phase
transactions (Days 1-60) are loaded. Simulation-phase CSV rows are ignored at
runtime (kept on disk only as a reference execution). The historical deliveries
seed each supplier's KPI history so Betsy starts sim day 1 with real scores.
"""
from __future__ import annotations

import csv
from datetime import date

from app.config.operator_config import DEFAULT_CONFIG
from app.config.settings import DATA_DIR
from app.db.models import (
    Delivery, Invoice, KpiSnapshot, OperatorConfig, Product, PurchaseOrder,
    SimState, Supplier, SupplierProduct,
)
from app.db.session import get_session, init_db
from app.scoring.engine import recompute_all_scores, snapshot_values
from app.util import HISTORICAL_END_DAY, date_to_day


def _read(name: str) -> list[dict]:
    with open(DATA_DIR / name, newline="") as f:
        return list(csv.DictReader(f))


def _bool(v: str) -> bool:
    return str(v).strip().lower() == "true"


def _date(v: str) -> date | None:
    v = (v or "").strip()
    return date.fromisoformat(v) if v else None


def load_all(reset: bool = True) -> None:
    init_db(drop=reset)
    with get_session() as s:
        _load_suppliers(s)
        _load_products(s)
        _load_supplier_products(s)
        _load_historical_transactions(s)
        _seed_kpi_history(s)
        recompute_all_scores(s, DEFAULT_CONFIG["weights"])
        s.add(OperatorConfig(version=1, data=DEFAULT_CONFIG))
        s.add(SimState(id=1, current_day=HISTORICAL_END_DAY, status="idle",
                       message="Loaded. Ready to run."))
    print("Dataset loaded; supplier scores seeded from 60 days of history.")


def _load_suppliers(s) -> None:
    for r in _read("suppliers.csv"):
        s.add(Supplier(
            supplier_id=r["supplier_id"], name=r["name"],
            category_focus=r["category_focus"], price_tier=r["price_tier"],
            base_lead_time_days=int(r["base_lead_time_days"]),
            quality_score=float(r["quality_score"]),
            default_moq=int(r["default_moq"]), payment_terms=r["payment_terms"],
            unavailable_from_date=_date(r.get("unavailable_from_date", "")),
            notes=r.get("notes", ""),
            # Synthetic sensitive data (privacy demo — never sent to the LLM)
            bank_details=f"IBAN NL{abs(hash(r['supplier_id'])) % 10**16:016d}",
            contact=f"orders@{r['name'].lower().replace(' ', '')}.example",
        ))
    s.flush()


def _load_products(s) -> None:
    for r in _read("products.csv"):
        s.add(Product(
            product_id=r["product_id"], name=r["name"], category=r["category"],
            abc_class=r["abc_class"], unit=r["unit"],
            base_unit_price=float(r["base_unit_price"]),
            daily_usage_rate=int(r["daily_usage_rate"]),
            safety_stock=int(r["safety_stock"]),
            default_lead_time_days=int(r["default_lead_time_days"]),
            reorder_point=int(r["reorder_point"]),
            stock_at_sim_start=int(r["stock_at_sim_start"]),
            current_stock=int(r["stock_at_sim_start"]),
        ))
    s.flush()


def _load_supplier_products(s) -> None:
    for r in _read("supplier_products.csv"):
        s.add(SupplierProduct(
            supplier_id=r["supplier_id"], product_id=r["product_id"],
            unit_price=float(r["unit_price"]),
            supplier_lead_time_days=int(r["supplier_lead_time_days"]),
            supplier_moq=int(r["supplier_moq"]),
        ))
    s.flush()

def _load_historical_transactions(s) -> None:
    """POs/deliveries/invoices with phase=historical only."""
    
    # 1. Load and flush Purchase Orders FIRST
    for r in _read("purchase_orders.csv"):
        if r["phase"] != "historical":
            continue
        placed = date.fromisoformat(r["placed_date"])
        exp = date.fromisoformat(r["expected_delivery_date"])
        s.add(PurchaseOrder(
            po_id=r["po_id"], supplier_id=r["supplier_id"], product_id=r["product_id"],
            placed_day=date_to_day(placed), placed_date=placed,
            expected_delivery_day=date_to_day(exp), expected_delivery_date=exp,
            quantity=int(r["quantity"]), unit_price=float(r["unit_price"]),
            total_amount=float(r["total_amount"]), status=r["status"],
            phase="historical", notes=r.get("notes", ""),
        ))
    
    s.flush()  

    # 2. Load and flush Deliveries SECOND
    for r in _read("delivery_records.csv"):
        if r["phase"] != "historical":
            continue
        exp = date.fromisoformat(r["expected_delivery_date"])
        act = date.fromisoformat(r["actual_delivery_date"])
        s.add(Delivery(
            delivery_id=r["delivery_id"], po_id=r["po_id"], supplier_id=r["supplier_id"],
            product_id=r["product_id"],
            expected_delivery_day=date_to_day(exp), expected_delivery_date=exp,
            actual_delivery_day=date_to_day(act), actual_delivery_date=act,
            quantity_ordered=int(r["quantity_ordered"]),
            quantity_received=int(r["quantity_received"]),
            on_time=_bool(r["on_time"]), quality_pass=_bool(r["quality_pass"]),
            defects_count=int(r["defects_count"]), phase="historical",
            notes=r.get("notes", ""),
        ))
        
    s.flush()  

    # 3. Load and flush Invoices LAST
    for r in _read("invoices.csv"):
        if r["phase"] != "historical":
            continue
        inv = date.fromisoformat(r["invoice_date"])
        s.add(Invoice(
            invoice_id=r["invoice_id"], invoice_number=r["invoice_number"],
            po_id=r["po_id"], supplier_id=r["supplier_id"],
            invoice_day=date_to_day(inv), invoice_date=inv,
            amount=float(r["amount"]), po_amount=float(r["po_amount"]),
            matches_po=_bool(r["matches_po"]), is_duplicate=_bool(r["is_duplicate"]),
            payment_status=r["payment_status"], anomaly_flag=r.get("anomaly_flag", ""),
            phase="historical",
        ))
        
    s.flush()


def _seed_kpi_history(s) -> None:
    """Build one KPI snapshot per historical delivery so scores reflect track record."""
    from sqlalchemy import select

    pos = {p.po_id: p for p in s.execute(select(PurchaseOrder)).scalars()}
    invoices_by_po: dict[str, Invoice] = {}
    for inv in s.execute(select(Invoice)).scalars():
        invoices_by_po.setdefault(inv.po_id, inv)

    for d in s.execute(select(Delivery).order_by(Delivery.actual_delivery_day)).scalars():
        po = pos.get(d.po_id)
        if not po:
            continue
        inv = invoices_by_po.get(d.po_id)
        inv_unit = (inv.amount / d.quantity_ordered) if (inv and d.quantity_ordered) else None
        vals = snapshot_values(
            on_time=d.on_time, defects=d.defects_count,
            qty_ordered=d.quantity_ordered, qty_received=d.quantity_received,
            expected_day=d.expected_delivery_day, actual_day=d.actual_delivery_day,
            po_unit_price=po.unit_price, invoice_unit_price=inv_unit,
        )
        s.add(KpiSnapshot(
            supplier_id=d.supplier_id, delivery_id=d.delivery_id,
            created_day=d.actual_delivery_day, **vals,
        ))
    s.flush()


if __name__ == "__main__":
    load_all(reset=True)