"""Default operator config (Jenny's dials, memory store S6).

Seeded into the DB on first load; editable live in the dashboard config editor.
Caps are calibrated against the synthetic dataset so that ~95%+ of POs auto-approve
and the high-value scenarios (5.1 budget, 2.3 motor shortage) escalate to Jenny.
"""
from __future__ import annotations

# Scoring weights (Supplier scoring.md). Must sum to 1.0.
DEFAULT_WEIGHTS = {
    "otd": 0.35,            # on-time delivery
    "por": 0.30,            # perfect order rate
    "lead_time_var": 0.15,  # lower is better
    "price_stability": 0.20,  # lower is better
}

DEFAULT_CONFIG = {
    # Spending caps (USD)
    "per_po_cap": 2000.0,       # a single PO above this needs Jenny's approval
    "monthly_cap": 50000.0,     # month-to-date spend ceiling
    # Lists
    "blocked_suppliers": [],    # supplier_ids Betsy may never select
    # Scoring weights (per above)
    "weights": DEFAULT_WEIGHTS,
    # Tolerances (Failure modes F1/F3/F5)
    "late_tolerance_days": 0,       # F1: lateness beyond this dings the score
    "price_overrun_pct": 0.05,      # F3: invoice over PO by >5% is an anomaly
    "price_overrun_hard_pct": 1.0,  # F3: >2x cap (i.e. +100%) forces escalation
    "excess_stock_multiple": 3.0,   # F5: stock > 3x monthly usage = overstock
    # Notifications
    "notify_channel": "dashboard",
}
