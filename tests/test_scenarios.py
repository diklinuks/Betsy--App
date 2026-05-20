"""Unit tests for scenario scheduling helpers (pure)."""
from app.sim.scenarios import (
    SCENARIOS, active_delivery_override, active_invoice_override, world_scenarios_for_day,
)


def test_demand_spike_on_day_22():
    hits = world_scenarios_for_day(22)
    assert any(sc["type"] == "demand_spike" and sc["product"] == "P03" for sc in hits)


def test_bankruptcy_on_day_50():
    hits = world_scenarios_for_day(50)
    assert any(sc["type"] == "bankruptcy" and sc["supplier"] == "S12" for sc in hits)


def test_delivery_override_fires_in_window_once():
    fired: set = set()
    ov = active_delivery_override(15, fired)          # late_delivery window starts day 14
    assert ov is not None and ov["type"] == "late_delivery"
    fired.add(ov["id"])
    # same window, already fired -> not returned again
    assert active_delivery_override(15, fired) != ov or active_delivery_override(15, fired) is None


def test_invoice_override_window():
    ov = active_invoice_override(25, set())
    assert ov is not None and ov["type"] == "invoice_mismatch"


def test_all_15_scenarios_present():
    ids = {sc["id"] for sc in SCENARIOS}
    # groups 2-4 injected; 1.x/5.x emerge from behaviour
    for required in {"2.1", "2.2", "2.3", "3.1", "3.2", "3.3", "3.4", "4.1", "4.2", "4.3"}:
        assert required in ids
