"""Persist fetch ladder telemetry (DB-free strategy → caller records here)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cost_model import aggregate_savings, savings_for_event
from fetch_strategy import registrable_domain


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _db():
    from db import _get_db

    return _get_db()


def record_fetch_event(
    *,
    user_id: Optional[str],
    job_id: Optional[str],
    url: str,
    provider: Optional[str],
    source: Optional[str],
    final_tier: str,
    attempts: List[str],
    profile_hit: bool = False,
) -> None:
    domain = registrable_domain(url)
    costs = savings_for_event(attempts=attempts, final_tier=final_tier, profile_hit=profile_hit)
    conn = _db()
    try:
        conn.execute(
            """
            INSERT INTO fetch_events
              (id, user_id, job_id, url, domain, provider, source, final_tier,
               attempts_json, profile_hit, baseline_cost, actual_cost, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                user_id,
                job_id,
                url,
                domain,
                provider,
                source,
                final_tier,
                json.dumps(list(attempts or [])),
                1 if profile_hit else 0,
                costs["baseline_cost"],
                costs["actual_cost"],
                _utcnow(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_fetch_savings(user_id: str, days: int = 30) -> Dict[str, Any]:
    days = max(1, min(365, int(days)))
    conn = _db()
    try:
        rows = conn.execute(
            """
            SELECT domain, baseline_cost, actual_cost, final_tier, attempts_json, created_at
            FROM fetch_events
            WHERE user_id = ?
              AND datetime(replace(created_at, 'T', ' ')) >= datetime('now', ?)
            ORDER BY created_at DESC
            LIMIT 5000
            """,
            (user_id, f"-{days} days"),
        ).fetchall()
        events = [
            {
                "domain": r["domain"],
                "baseline_cost": r["baseline_cost"],
                "actual_cost": r["actual_cost"],
                "final_tier": r["final_tier"],
            }
            for r in rows
        ]
        out = aggregate_savings(events)
        out["window_days"] = days
        return out
    finally:
        conn.close()
