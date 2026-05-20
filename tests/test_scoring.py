"""Unit tests for the pure scoring logic (no DB needed)."""
from app.config.operator_config import DEFAULT_WEIGHTS
from app.scoring.engine import composite, normalize, snapshot_values


def test_normalize_higher_is_better():
    assert normalize(10, 0, 10, higher_is_better=True) == 1.0
    assert normalize(0, 0, 10, higher_is_better=True) == 0.0
    assert normalize(5, 0, 10, higher_is_better=True) == 0.5


def test_normalize_lower_is_better_flips():
    assert normalize(0, 0, 10, higher_is_better=False) == 1.0
    assert normalize(10, 0, 10, higher_is_better=False) == 0.0


def test_normalize_no_spread_returns_one():
    assert normalize(5, 5, 5, higher_is_better=True) == 1.0
    assert normalize(5, 5, 5, higher_is_better=False) == 1.0


def test_composite_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_composite_perfect_supplier():
    assert composite(1.0, 1.0, 1.0, 1.0, DEFAULT_WEIGHTS) == 1.0


def test_composite_in_range():
    s = composite(0.8, 0.7, 0.6, 0.9, DEFAULT_WEIGHTS)
    assert 0.0 <= s <= 1.0


def test_snapshot_perfect_order():
    v = snapshot_values(on_time=True, defects=0, qty_ordered=100, qty_received=100,
                        expected_day=10, actual_day=10, po_unit_price=1.0,
                        invoice_unit_price=1.0)
    assert v == {"otd": 1.0, "por": 1.0, "lead_time_var": 0.0, "price_dev": 0.0}


def test_snapshot_late_defective_short():
    v = snapshot_values(on_time=False, defects=5, qty_ordered=100, qty_received=90,
                        expected_day=10, actual_day=13, po_unit_price=2.0,
                        invoice_unit_price=2.2)
    assert v["otd"] == 0.0
    assert v["por"] == 0.0
    assert v["lead_time_var"] == 3.0
    assert round(v["price_dev"], 2) == 0.10
