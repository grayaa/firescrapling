"""API keys and usage accounting. Keys are hashed at rest (sha256); plaintext returned once on create."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Any, Dict, List, Optional

from db import _get_db


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def key_hint_from_value(key_value: str) -> str:
    if not key_value or len(key_value) <= 10:
        return "fs_****"
    return f"{key_value[:6]}…{key_value[-4:]}"


def mask_key_value(key_value: str) -> str:
    """Display mask for a plaintext key (create response) or stored hint."""
    if not key_value:
        return "fs_****"
    if "…" in key_value or "..." in key_value:
        return key_value
    return key_hint_from_value(key_value)


def create_api_key(user_id: str, name: str) -> Dict:
    conn = _get_db()
    try:
        key_id = str(uuid.uuid4())
        key_value = f"fs_{secrets.token_urlsafe(32)}"
        digest = hash_api_key(key_value)
        hint = key_hint_from_value(key_value)
        # key_value column stores the hash (UNIQUE); plaintext never persisted.
        conn.execute(
            "INSERT INTO api_keys (id, user_id, key_value, key_hash, key_hint, name) VALUES (?, ?, ?, ?, ?, ?)",
            (key_id, user_id, digest, digest, hint, name),
        )
        conn.commit()
        return {"success": True, "key": {"id": key_id, "value": key_value, "name": name, "hint": hint}}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_api_keys(user_id: str) -> List[Dict]:
    """List keys without plaintext. `key_value` is the hash (legacy column); prefer `key_hint`."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, user_id, key_hash, key_hint, name, last_used, created_at FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    out: List[Dict] = []
    for r in rows:
        d = dict(r)
        # Compatibility for older callers that read key_value: expose hint only, never the hash as a "value".
        d["key_value"] = d.get("key_hint") or "fs_****"
        out.append(d)
    return out


def list_api_keys_masked(user_id: str) -> List[Dict[str, Any]]:
    """API key list with key_value masked (never expose full secret after creation)."""
    out: List[Dict[str, Any]] = []
    for r in get_api_keys(user_id):
        d = dict(r)
        preview = d.pop("key_hint", None) or d.pop("key_value", "") or "fs_****"
        d.pop("key_hash", None)
        d.pop("key_value", None)
        d["key_preview"] = preview if ("…" in str(preview) or str(preview).startswith("fs_")) else mask_key_value(str(preview))
        out.append(d)
    return out


def delete_api_key(user_id: str, key_id: str) -> Dict:
    conn = _get_db()
    cur = conn.execute("DELETE FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
    conn.commit()
    conn.close()
    return {"success": cur.rowcount > 0}


def get_api_usage(user_id: str, limit: int = 100) -> List[Dict]:
    conn = _get_db()
    rows = conn.execute(
        """
        SELECT u.*, k.name as key_name
        FROM api_usage u
        LEFT JOIN api_keys k ON u.key_id = k.id
        WHERE u.user_id = ?
        ORDER BY u.created_at DESC LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_usage_summary(user_id: str, days: int = 30) -> Dict[str, Any]:
    """Aggregate api_usage + jobs for the dashboard overview (single user, last N days)."""
    days = max(1, min(int(days), 365))
    window = f"-{days} days"
    conn = _get_db()
    try:
        totals = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS ok,
                   AVG(response_time_ms) AS avg_ms
            FROM api_usage
            WHERE user_id = ? AND created_at >= datetime('now', ?)
            """,
            (user_id, window),
        ).fetchone()
        total = int(totals["total"] or 0)
        ok = int(totals["ok"] or 0)

        # p95 without window functions: offset into the sorted latency list.
        p95 = 0
        if total:
            offset = max(0, int(total * 0.95) - 1)
            row = conn.execute(
                """
                SELECT response_time_ms FROM api_usage
                WHERE user_id = ? AND created_at >= datetime('now', ?)
                ORDER BY response_time_ms LIMIT 1 OFFSET ?
                """,
                (user_id, window, offset),
            ).fetchone()
            p95 = int((row["response_time_ms"] if row else 0) or 0)

        daily = [
            {
                "date": r["day"],
                "success": int(r["success"] or 0),
                "failed": int(r["failed"] or 0),
            }
            for r in conn.execute(
                """
                SELECT date(created_at) AS day,
                       SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS success,
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS failed
                FROM api_usage
                WHERE user_id = ? AND created_at >= datetime('now', ?)
                GROUP BY day ORDER BY day
                """,
                (user_id, window),
            ).fetchall()
        ]

        by_endpoint = [
            {
                "endpoint": r["endpoint"],
                "requests": int(r["requests"] or 0),
                "success_rate": round(100.0 * int(r["ok"] or 0) / int(r["requests"]), 1)
                if int(r["requests"] or 0)
                else 0.0,
            }
            for r in conn.execute(
                """
                SELECT endpoint, COUNT(*) AS requests,
                       SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS ok
                FROM api_usage
                WHERE user_id = ? AND created_at >= datetime('now', ?)
                GROUP BY endpoint ORDER BY requests DESC
                """,
                (user_id, window),
            ).fetchall()
        ]

        recent_jobs = [
            {
                "id": r["id"],
                "type": r["type"],
                "url": r["url"],
                "status": r["status"],
                "pages": int(r["pages"] or 0),
                "created_at": r["created_at"],
            }
            for r in conn.execute(
                """
                SELECT j.id, j.type, j.url, j.status, j.created_at,
                       (SELECT COUNT(*) FROM results WHERE job_id = j.id) AS pages
                FROM jobs j
                WHERE j.user_id = ?
                ORDER BY j.created_at DESC LIMIT 8
                """,
                (user_id,),
            ).fetchall()
        ]

        pages_crawled = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM results r
                JOIN jobs j ON r.job_id = j.id
                WHERE j.user_id = ? AND r.created_at >= datetime('now', ?)
                """,
                (user_id, window),
            ).fetchone()["c"]
            or 0
        )
        active_keys = int(
            conn.execute("SELECT COUNT(*) AS c FROM api_keys WHERE user_id = ?", (user_id,)).fetchone()["c"] or 0
        )

        return {
            "window_days": days,
            "total_requests": total,
            "failed_requests": total - ok,
            "success_rate": round(100.0 * ok / total, 1) if total else 100.0,
            "avg_latency_ms": int(totals["avg_ms"] or 0),
            "p95_latency_ms": p95,
            "pages_crawled": pages_crawled,
            "active_keys": active_keys,
            "daily": daily,
            "by_endpoint": by_endpoint,
            "recent_jobs": recent_jobs,
        }
    finally:
        conn.close()


def resolve_api_key(raw_key: str) -> Optional[Dict[str, str]]:
    if not raw_key or not raw_key.strip():
        return None
    stripped = raw_key.strip()
    digest = hash_api_key(stripped)
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id FROM api_keys WHERE key_hash = ? OR key_value = ?",
            (digest, digest),
        ).fetchone()
        if row:
            return {"key_id": row["id"], "user_id": row["user_id"]}
        # Legacy plaintext rows (pre-hash migration) — match then upgrade in place.
        row = conn.execute(
            "SELECT id, user_id, key_value FROM api_keys WHERE key_value = ?",
            (stripped,),
        ).fetchone()
        if not row:
            return None
        hint = key_hint_from_value(stripped)
        conn.execute(
            "UPDATE api_keys SET key_hash = ?, key_hint = ?, key_value = ? WHERE id = ?",
            (digest, hint, digest, row["id"]),
        )
        conn.commit()
        return {"key_id": row["id"], "user_id": row["user_id"]}
    finally:
        conn.close()


def touch_api_key_last_used(key_id: str) -> None:
    conn = _get_db()
    try:
        conn.execute("UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE id = ?", (key_id,))
        conn.commit()
    finally:
        conn.close()


def record_api_usage(
    user_id: Optional[str],
    key_id: Optional[str],
    endpoint: str,
    status_code: int,
    response_time_ms: int,
) -> None:
    if not user_id:
        return
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO api_usage (id, user_id, key_id, endpoint, status_code, response_time_ms) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, key_id, endpoint, status_code, response_time_ms),
        )
        conn.commit()
    finally:
        conn.close()
