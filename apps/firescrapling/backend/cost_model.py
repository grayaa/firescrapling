"""Estimated fetch-cost model (bake-off weights). UI must label as estimated."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Relative credit weights vs a typical Scrape.do ASP/super request ≈ 5–25 credits.
# Baseline for "savings" is always treating the page as sf_asp (paid anti-bot).
TIER_WEIGHTS: Dict[str, float] = {
    "local": 0.0,
    "sf_static": 1.0,
    "sf_js": 5.0,
    "sf_asp": 25.0,
    "sf_residential": 75.0,
    "default": 1.0,
    "explicit": 25.0,
    "unknown": 25.0,
}

BASELINE_TIER = "sf_asp"


def weight_for_tier(tier: str) -> float:
    return float(TIER_WEIGHTS.get(tier, TIER_WEIGHTS["unknown"]))


def estimate_attempt_cost(attempts: List[str], final_tier: str) -> float:
    """Sum modeled cost of each ladder step (failed probes + success)."""
    if not attempts:
        return weight_for_tier(final_tier)
    return sum(weight_for_tier(t) for t in attempts)


def estimate_baseline_cost() -> float:
    return weight_for_tier(BASELINE_TIER)


def savings_for_event(
    *,
    attempts: List[str],
    final_tier: str,
    profile_hit: bool = False,
) -> Dict[str, float]:
    actual = estimate_attempt_cost(attempts, final_tier)
    # Profile hit: we skipped cheap probes — still charge final tier only once.
    if profile_hit and attempts:
        actual = weight_for_tier(attempts[-1] if attempts else final_tier)
    baseline = estimate_baseline_cost()
    saved = max(0.0, baseline - actual)
    pct = (saved / baseline * 100.0) if baseline > 0 else 0.0
    return {
        "baseline_cost": baseline,
        "actual_cost": actual,
        "saved_cost": saved,
        "savings_pct": pct,
    }


def aggregate_savings(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_base = 0.0
    total_actual = 0.0
    by_domain: Dict[str, Dict[str, float]] = {}
    for ev in events:
        base = float(ev.get("baseline_cost") or estimate_baseline_cost())
        actual = float(ev.get("actual_cost") or 0.0)
        domain = str(ev.get("domain") or "unknown")
        total_base += base
        total_actual += actual
        bucket = by_domain.setdefault(
            domain, {"baseline_cost": 0.0, "actual_cost": 0.0, "events": 0.0}
        )
        bucket["baseline_cost"] += base
        bucket["actual_cost"] += actual
        bucket["events"] += 1.0

    saved = max(0.0, total_base - total_actual)
    pct = (saved / total_base * 100.0) if total_base > 0 else 0.0
    domains = []
    for domain, b in sorted(by_domain.items(), key=lambda x: -x[1]["baseline_cost"]):
        d_saved = max(0.0, b["baseline_cost"] - b["actual_cost"])
        d_pct = (d_saved / b["baseline_cost"] * 100.0) if b["baseline_cost"] else 0.0
        domains.append(
            {
                "domain": domain,
                "events": int(b["events"]),
                "baseline_cost": round(b["baseline_cost"], 2),
                "actual_cost": round(b["actual_cost"], 2),
                "saved_cost": round(d_saved, 2),
                "savings_pct": round(d_pct, 1),
            }
        )
    return {
        "estimated": True,
        "baseline_tier": BASELINE_TIER,
        "events": len(events),
        "baseline_cost": round(total_base, 2),
        "actual_cost": round(total_actual, 2),
        "saved_cost": round(saved, 2),
        "savings_pct": round(pct, 1),
        "by_domain": domains,
    }
