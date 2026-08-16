"""Unit tests for estimated fetch cost / savings model."""
from __future__ import annotations

from cost_model import aggregate_savings, estimate_attempt_cost, savings_for_event


def test_local_beats_baseline():
    s = savings_for_event(attempts=["local"], final_tier="local")
    assert s["actual_cost"] == 0
    assert s["savings_pct"] > 90


def test_asp_no_savings():
    s = savings_for_event(attempts=["sf_asp"], final_tier="sf_asp")
    assert s["saved_cost"] == 0
    assert s["savings_pct"] == 0


def test_ladder_sums_attempts():
    # local + static + js
    cost = estimate_attempt_cost(["local", "sf_static", "sf_js"], "sf_js")
    assert cost == 0 + 1 + 5


def test_aggregate_by_domain():
    events = [
        {"domain": "a.com", "baseline_cost": 25, "actual_cost": 0},
        {"domain": "a.com", "baseline_cost": 25, "actual_cost": 5},
        {"domain": "b.com", "baseline_cost": 25, "actual_cost": 25},
    ]
    out = aggregate_savings(events)
    assert out["estimated"] is True
    assert out["events"] == 3
    assert out["by_domain"][0]["domain"] == "a.com"
    assert out["savings_pct"] > 0
