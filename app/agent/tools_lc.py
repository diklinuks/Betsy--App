"""Read tools wired as in-process LangChain tools.

Used when BETSY_TOOLS_TRANSPORT=local and for the LangGraph Studio graph. The MCP
path (default) exposes the same tools over MCP; this is the identical tool surface
without the subprocess transport.
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.db.session import get_session
from app.tools import functions as f


@tool
def inventory_read(sku_id: str) -> dict:
    """Current stock, daily usage, reorder point and days-of-cover for one SKU."""
    with get_session() as s:
        return f.inventory_read(s, sku_id)


@tool
def supplier_catalogue(product_id: str) -> list:
    """Active, non-blocked suppliers for a product with unit price, lead time, MOQ and
    current reliability score, sorted best-score first."""
    with get_session() as s:
        return f.supplier_catalogue(s, product_id)


@tool
def supplier_history(supplier_id: str) -> dict:
    """Recent KPI history for a supplier: on-time rate, perfect-order rate, lead-time
    variance and price deviation."""
    with get_session() as s:
        return f.supplier_history(s, supplier_id)


@tool
def config_read() -> dict:
    """Operator config: per-PO cap, monthly cap, blocked suppliers, scoring weights."""
    with get_session() as s:
        return f.config_read(s)


@tool
def decision_search(query: str, k: int = 5) -> list:
    """Find past decisions and learned lessons similar to the current situation."""
    with get_session() as s:
        return f.decision_search(s, query, k)


READ_TOOLS = [inventory_read, supplier_catalogue, supplier_history, config_read, decision_search]
