"""SQLAlchemy models — Betsy's memory layer (Memory layer.md, S3-S11 + runtime state).

Structured memory lives in normal SQL tables. Decision-rationale text is embedded
into `memory_embeddings` (pgvector) for semantic recall (R6/R7).
"""
from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config.settings import EMBEDDING_DIM


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# S3 — Suppliers
# --------------------------------------------------------------------------- #
class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category_focus: Mapped[str] = mapped_column(String)  # ";"-separated
    price_tier: Mapped[str] = mapped_column(String)
    base_lead_time_days: Mapped[int] = mapped_column(Integer)
    default_moq: Mapped[int] = mapped_column(Integer)
    payment_terms: Mapped[str] = mapped_column(String)
    unavailable_from_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(String, default="")

    # Intrinsic reliability seed (from dataset) — used by the world-simulator to
    # generate delivery outcomes for Betsy's live POs. NOT the score Betsy ranks on.
    quality_score: Mapped[float] = mapped_column(Float, default=0.85)

    # Betsy-maintained state
    current_score: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String, default="active")  # active|inactive

    # Sensitive — never projected to the LLM or embedded (Ethics: Privacy)
    bank_details: Mapped[str] = mapped_column(String, default="")
    contact: Mapped[str] = mapped_column(String, default="")


# --------------------------------------------------------------------------- #
# S4 — Products / SKUs
# --------------------------------------------------------------------------- #
class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    abc_class: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)
    base_unit_price: Mapped[float] = mapped_column(Float)
    daily_usage_rate: Mapped[int] = mapped_column(Integer)
    safety_stock: Mapped[int] = mapped_column(Integer)
    default_lead_time_days: Mapped[int] = mapped_column(Integer)
    reorder_point: Mapped[int] = mapped_column(Integer)
    stock_at_sim_start: Mapped[int] = mapped_column(Integer)

    # Live state during simulation
    current_stock: Mapped[int] = mapped_column(Integer, default=0)


class SupplierProduct(Base):
    __tablename__ = "supplier_products"
    __table_args__ = (UniqueConstraint("supplier_id", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"))
    unit_price: Mapped[float] = mapped_column(Float)
    supplier_lead_time_days: Mapped[int] = mapped_column(Integer)
    supplier_moq: Mapped[int] = mapped_column(Integer)


# --------------------------------------------------------------------------- #
# S7 — Purchase orders
# --------------------------------------------------------------------------- #
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id: Mapped[str] = mapped_column(String, primary_key=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"))
    placed_day: Mapped[int] = mapped_column(Integer)
    placed_date: Mapped[date] = mapped_column(Date)
    expected_delivery_day: Mapped[int] = mapped_column(Integer)
    expected_delivery_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="open")  # open|received|cancelled|rejected
    phase: Mapped[str] = mapped_column(String, default="simulation")
    decision_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, default="")


# --------------------------------------------------------------------------- #
# S8 — Deliveries
# --------------------------------------------------------------------------- #
class Delivery(Base):
    __tablename__ = "deliveries"

    delivery_id: Mapped[str] = mapped_column(String, primary_key=True)
    po_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.po_id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"))
    expected_delivery_day: Mapped[int] = mapped_column(Integer)
    actual_delivery_day: Mapped[int] = mapped_column(Integer)
    expected_delivery_date: Mapped[date] = mapped_column(Date)
    actual_delivery_date: Mapped[date] = mapped_column(Date)
    quantity_ordered: Mapped[int] = mapped_column(Integer)
    quantity_received: Mapped[int] = mapped_column(Integer)
    on_time: Mapped[bool] = mapped_column(Boolean)
    quality_pass: Mapped[bool] = mapped_column(Boolean)
    defects_count: Mapped[int] = mapped_column(Integer, default=0)
    phase: Mapped[str] = mapped_column(String, default="simulation")
    notes: Mapped[str] = mapped_column(String, default="")


# --------------------------------------------------------------------------- #
# S9 — Invoices  (dedupe key = duplicate-invoice check, F6)
# --------------------------------------------------------------------------- #
class Invoice(Base):
    __tablename__ = "invoices"
    # No DB unique constraint on (invoice_number, supplier_id): a duplicate invoice
    # must be storable so it can be FLAGGED and held (F6). Dedupe is a logic check
    # in invoice_match, not a hard DB block.

    invoice_id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String)
    po_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.po_id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))
    invoice_day: Mapped[int] = mapped_column(Integer)
    invoice_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Float)
    po_amount: Mapped[float] = mapped_column(Float)
    matches_po: Mapped[bool] = mapped_column(Boolean)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_status: Mapped[str] = mapped_column(String, default="paid")  # paid|held
    anomaly_flag: Mapped[str] = mapped_column(String, default="")
    phase: Mapped[str] = mapped_column(String, default="simulation")


# --------------------------------------------------------------------------- #
# S5 — KPI snapshots (append-only, one per delivery)
# --------------------------------------------------------------------------- #
class KpiSnapshot(Base):
    __tablename__ = "kpi_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))
    delivery_id: Mapped[str] = mapped_column(ForeignKey("deliveries.delivery_id"))
    created_day: Mapped[int] = mapped_column(Integer)
    otd: Mapped[float] = mapped_column(Float)              # 1.0 on time, 0.0 late
    por: Mapped[float] = mapped_column(Float)              # 1.0 perfect order
    lead_time_var: Mapped[float] = mapped_column(Float)    # |promised - actual| days
    price_dev: Mapped[float] = mapped_column(Float)        # % deviation invoice vs PO


# --------------------------------------------------------------------------- #
# S10 — Decision audit log (append-only, audit-grade)
# --------------------------------------------------------------------------- #
class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String, primary_key=True)
    sim_day: Mapped[int] = mapped_column(Integer)
    trigger_type: Mapped[str] = mapped_column(String)     # reorder|delivery|invoice|stockout
    product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    candidates: Mapped[list] = mapped_column(JSONB, default=list)   # [{supplier_id, score, price, lead}]
    chosen_supplier: Mapped[str | None] = mapped_column(String, nullable=True)
    chosen_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    alternatives: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    action: Mapped[str] = mapped_column(String, default="")         # po_generated|escalated|...
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)     # stock <= safety at decision
    attribution: Mapped[str] = mapped_column(String, default="autonomous")  # autonomous|post-approval
    config_version: Mapped[int] = mapped_column(Integer, default=1)
    outcome: Mapped[dict | None] = mapped_column(JSONB, nullable=True)      # filled when PO closes
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# --------------------------------------------------------------------------- #
# S11 — Memory embeddings (pgvector): rationale + reflection + rejection lessons
# --------------------------------------------------------------------------- #
class MemoryEmbedding(Base):
    __tablename__ = "memory_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String)  # rationale|reflection|rejection
    decision_id: Mapped[str | None] = mapped_column(String, nullable=True)
    supplier_id: Mapped[str | None] = mapped_column(String, nullable=True)
    product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_day: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBEDDING_DIM))


# --------------------------------------------------------------------------- #
# S6 — Operator config (versioned; old versions retained for audit, W5)
# --------------------------------------------------------------------------- #
class OperatorConfig(Base):
    __tablename__ = "operator_config"

    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# --------------------------------------------------------------------------- #
# S2 — Pending approvals (cleared when Jenny answers)
# --------------------------------------------------------------------------- #
class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    decision_id: Mapped[str] = mapped_column(String, primary_key=True)
    sim_day: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[str] = mapped_column(String)
    proposal: Mapped[dict] = mapped_column(JSONB)   # {supplier_id, quantity, unit_price, total, reason}
    reason_needed: Mapped[str] = mapped_column(String)  # why escalated
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|approved|rejected
    jenny_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# --------------------------------------------------------------------------- #
# Traceability — append-only event stream (one row per meaningful sim action)
# --------------------------------------------------------------------------- #
class Event(Base):
    """Every meaningful thing Betsy does, captured so the process is visible.

    Previously the per-day `world.events` list was discarded each tick; this table
    persists it for the live Activity feed AND the static replay export.
    `severity` drives colour in the UI; the *_id columns let the UI cross-link an
    event to its decision / delivery / invoice / supplier / product.
    """
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    abs_day: Mapped[int] = mapped_column(Integer, index=True)
    sim_day: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String)        # reorder|proposal|po|delivery|invoice|...
    severity: Mapped[str] = mapped_column(String, default="info")  # info|good|warn|bad|action
    title: Mapped[str] = mapped_column(String)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    supplier_id: Mapped[str | None] = mapped_column(String, nullable=True)
    po_id: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# --------------------------------------------------------------------------- #
# Runtime — simulation state (one row, for the dashboard)
# --------------------------------------------------------------------------- #
class SimState(Base):
    __tablename__ = "sim_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    current_day: Mapped[int] = mapped_column(Integer, default=60)  # absolute day
    status: Mapped[str] = mapped_column(String, default="idle")    # idle|running|paused|finished|error
    message: Mapped[str] = mapped_column(String, default="")
    fired_scenarios: Mapped[list] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
