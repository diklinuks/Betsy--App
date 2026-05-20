"""Betsy's tools as an MCP server (Frameworks and MCP.md).

The real logic lives in app/tools/functions.py (plain, unit-testable functions);
this module is the thin MCP wrapper. Each tool opens its own DB session.

Run standalone (stdio):   python -m app.mcp_server.server
Inspect with the MCP CLI: mcp dev app/mcp_server/server.py
LangGraph consumes it via langchain-mcp-adapters (see app/agent/graph.py).
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.db.session import get_session
from app.tools import functions as f

mcp = FastMCP("betsy-tools")


# ----------------------------- READ TOOLS (LLM-facing) ----------------------------- #
@mcp.tool()
def inventory_read(sku_id: str) -> dict:
    """Current stock, daily usage, reorder point and days-of-cover for one SKU."""
    with get_session() as s:
        return f.inventory_read(s, sku_id)


@mcp.tool()
def supplier_catalogue(product_id: str) -> list[dict]:
    """Active, non-blocked suppliers for a product with unit price, lead time, MOQ and
    current reliability score, sorted best-score first."""
    with get_session() as s:
        return f.supplier_catalogue(s, product_id)


@mcp.tool()
def supplier_history(supplier_id: str) -> dict:
    """Recent KPI history for a supplier: on-time rate, perfect-order rate, lead-time
    variance and price deviation over the last deliveries."""
    with get_session() as s:
        return f.supplier_history(s, supplier_id)


@mcp.tool()
def config_read() -> dict:
    """Operator config: per-PO cap, monthly cap, blocked suppliers, scoring weights."""
    with get_session() as s:
        return f.config_read(s)


@mcp.tool()
def decision_search(query: str, k: int = 5) -> list[dict]:
    """Find past decisions and learned lessons similar to the current situation."""
    with get_session() as s:
        return f.decision_search(s, query, k)


# ----------------------------- WRITE TOOLS (also MCP-exposed) ----------------------------- #
@mcp.tool()
def po_generate(sku_id: str, supplier_id: str, quantity: int, unit_price: float,
                day: int = 61, sim_day: int = 1, approved: bool = False) -> dict:
    """Create a purchase order. Enforces blocked-supplier and spend caps; an over-cap
    PO returns needs_approval unless approved=True."""
    with get_session() as s:
        return f.po_generate(s, sku_id, supplier_id, quantity, unit_price,
                             day=day, sim_day=sim_day, approved=approved)


@mcp.tool()
def notify_human(message: str, needs_approval: bool = False) -> dict:
    """Send Jenny a notification or approval request."""
    with get_session() as s:
        return f.notify_human(s, message, needs_approval)


@mcp.tool()
def delivery_record(po_id: str, on_time: bool, quantity_received: int,
                    quality_pass: bool, defects: int, actual_day: int) -> dict:
    """Log a received delivery against its PO."""
    with get_session() as s:
        return f.delivery_record(s, po_id=po_id, on_time=on_time,
                                 quantity_received=quantity_received,
                                 quality_pass=quality_pass, defects=defects,
                                 actual_day=actual_day)


@mcp.tool()
def inventory_update(sku_id: str, received_qty: int) -> dict:
    """Apply a received delivery to a SKU's stock."""
    with get_session() as s:
        return f.inventory_update(s, sku_id, received_qty)


@mcp.tool()
def supplier_score_update(supplier_id: str, delivery_id: str) -> dict:
    """Append a KPI snapshot for a delivery and recompute the supplier's score."""
    with get_session() as s:
        return f.supplier_score_update(s, supplier_id, delivery_id)


@mcp.tool()
def invoice_match(invoice_id: str) -> dict:
    """Three-way match an invoice against its PO and delivery; flag mismatch/duplicate."""
    with get_session() as s:
        return f.invoice_match(s, invoice_id)


# decision_log is exposed for completeness but is normally called by the runner.
@mcp.tool()
def ping() -> str:
    """Health check — confirms the MCP server is up."""
    return "betsy-tools ok"


if __name__ == "__main__":
    mcp.run()
