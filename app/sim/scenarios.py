"""The 15 test scenarios (Test scenarios.md) as runtime injections for the LIVE world.

Two families:
  * WORLD events (deterministic, independent of Betsy's choices): demand spike,
    forced stockout, supplier bankruptcy, supplier shortage, invoice mismatch/duplicate.
  * DELIVERY overrides (attached to the first qualifying delivery in a window):
    late, wrong quantity, defect batch, partial delivery.

Decision-quality scenarios (5.1 budget, 5.2 conflicting criteria, 5.3 human override)
emerge from Betsy + the operator config + the human, not from injection.

sim_day N = absolute day 60 + N.
"""
from __future__ import annotations

# sim-day keyed scenario table
SCENARIOS = [
    # --- world events ---
    {"id": "2.1", "type": "demand_spike", "sim_day": 22, "product": "P03", "extra": 200},
    {"id": "2.2", "type": "force_stockout", "sim_day": 45, "product": "P08"},
    {"id": "3.4", "type": "bankruptcy", "sim_day": 50, "supplier": "S12"},
    {"id": "2.3", "type": "supplier_shortage", "sim_day": 35, "until_sim_day": 38,
     "supplier": "S04"},
    # --- delivery overrides (apply to first delivery arriving in [sim_day, sim_day+window]) ---
    {"id": "3.1", "type": "late_delivery", "sim_day": 14, "window": 8, "delay_days": 1},
    {"id": "3.2", "type": "wrong_quantity", "sim_day": 17, "window": 8, "short": 5},
    {"id": "3.3", "type": "defect", "sim_day": 40, "window": 8, "defect_units": 25},
    {"id": "4.3", "type": "partial_delivery", "sim_day": 28, "window": 8,
     "first_fraction": 0.6, "remainder_delay": 5},
    # --- invoice overrides (apply to first invoice issued in window) ---
    {"id": "4.1", "type": "invoice_mismatch", "sim_day": 25, "window": 6, "extra_pct": 0.12},
    {"id": "4.2", "type": "duplicate_invoice", "sim_day": 32, "window": 6},
]


def world_scenarios_for_day(sim_day: int) -> list[dict]:
    return [sc for sc in SCENARIOS
            if sc["type"] in ("demand_spike", "force_stockout", "bankruptcy", "supplier_shortage")
            and sc["sim_day"] == sim_day]


def active_delivery_override(sim_day: int, fired: set) -> dict | None:
    """First unfired delivery-override scenario whose window covers sim_day."""
    for sc in SCENARIOS:
        if sc["type"] not in ("late_delivery", "wrong_quantity", "defect", "partial_delivery"):
            continue
        if sc["id"] in fired:
            continue
        if sc["sim_day"] <= sim_day <= sc["sim_day"] + sc.get("window", 0):
            return sc
    return None


def active_invoice_override(sim_day: int, fired: set) -> dict | None:
    for sc in SCENARIOS:
        if sc["type"] not in ("invoice_mismatch", "duplicate_invoice"):
            continue
        if sc["id"] in fired:
            continue
        if sc["sim_day"] <= sim_day <= sc["sim_day"] + sc.get("window", 0):
            return sc
    return None
