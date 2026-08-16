"""Job lifecycle, logs, results, and webhook notify."""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from webhook_delivery import deliver_webhook

from db import _get_db

logger = logging.getLogger(__name__)


def _add_log(conn, job_id, content, progress=None):
    conn.execute(
        "INSERT INTO logs (job_id, content, progress) VALUES (?, ?, ?)",
        (job_id, content, progress),
    )
    conn.commit()


def _update_job_progress(conn: sqlite3.Connection, job_id: str, progress: int) -> None:
    p = min(100, max(0, int(progress)))
    conn.execute("UPDATE jobs SET progress = ? WHERE id = ?", (p, job_id))


def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_job_for_user(job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _notify_job_webhook(job_id: str, event: str, payload: Dict[str, Any]) -> None:
    row = get_job_by_id(job_id)
    if not row:
        return
    url = row.get("webhook_url")
    secret = row.get("webhook_secret")
    if not url or not secret:
        return
    body = {"job_id": job_id, **payload}
    try:
        from job_queue import enqueue_webhook

        enqueue_webhook(url, secret, event, body, f"{job_id}-{event}")
    except Exception:
        # Last resort: deliver inline if queue import/enqueue fails
        logger.exception("webhook enqueue failed; delivering inline job=%s", job_id)
        deliver_webhook(url, secret, event, body, f"{job_id}-{event}")


def create_job_with_idempotency(
    user_id: Optional[str],
    key_id: Optional[str],
    idempotency_key: Optional[str],
    endpoint: str,
    *,
    job_type: str,
    url: str,
    status: str,
    webhook_url: Optional[str] = None,
    webhook_secret: Optional[str] = None,
) -> str:
    """Create a job row; if idempotency_key matches an existing mapping, return that job_id instead."""
    conn = _get_db()
    ik = (idempotency_key or "").strip()
    try:
        if user_id and ik:
            row = conn.execute(
                "SELECT job_id FROM idempotency_keys WHERE user_id = ? AND idempotency_key = ? AND endpoint = ?",
                (user_id, ik, endpoint),
            ).fetchone()
            if row:
                return row["job_id"]
        conn.execute("BEGIN IMMEDIATE")
        try:
            job_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO jobs (id, user_id, type, url, status, progress, webhook_url, webhook_secret) VALUES (?,?,?,?,?,?,?,?)",
                (job_id, user_id, job_type, url, status, 0, webhook_url, webhook_secret),
            )
            if user_id and ik:
                conn.execute(
                    "INSERT INTO idempotency_keys (id, user_id, key_id, idempotency_key, job_id, endpoint) VALUES (?,?,?,?,?,?)",
                    (str(uuid.uuid4()), user_id, key_id, ik, job_id, endpoint),
                )
            conn.commit()
            return job_id
        except sqlite3.IntegrityError:
            conn.rollback()
            if user_id and ik:
                row = conn.execute(
                    "SELECT job_id FROM idempotency_keys WHERE user_id = ? AND idempotency_key = ? AND endpoint = ?",
                    (user_id, ik, endpoint),
                ).fetchone()
                if row:
                    return row["job_id"]
            raise
    finally:
        conn.close()


def get_job_results_for_user(job_id: str, user_id: str) -> Optional[List[Dict]]:
    if not get_job_for_user(job_id, user_id):
        return None
    return get_job_results(job_id)


def delete_job_for_user(job_id: str, user_id: str) -> bool:
    conn = _get_db()
    try:
        cur = conn.execute("DELETE FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_job_history(user_id: str = None, limit: int = 50) -> List[Dict]:
    conn = _get_db()
    rows = (
        conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        if user_id
        else conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    )
    conn.close()
    return [dict(r) for r in rows]


def get_job_results(
    job_id: str,
    offset: int = 0,
    limit: Optional[int] = None,
) -> List[Dict]:
    conn = _get_db()
    try:
        if limit is None:
            rows = conn.execute(
                "SELECT * FROM results WHERE job_id = ? ORDER BY created_at",
                (job_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM results WHERE job_id = ? ORDER BY created_at LIMIT ? OFFSET ?",
                (job_id, max(1, int(limit)), max(0, int(offset))),
            ).fetchall()
    finally:
        conn.close()
    res = []
    for r in rows:
        d = dict(r)
        meta = json.loads(d.pop("metadata_json", "{}") or "{}")
        d["metadata"] = meta
        if "structured_data" in meta:
            d["data"] = meta["structured_data"]
        res.append(d)
    return res


def count_job_results(job_id: str) -> int:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM results WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        return int(row["c"] if row else 0)
    finally:
        conn.close()


def get_job_logs(job_id: str) -> List[Dict]:
    conn = _get_db()
    rows = conn.execute(
        "SELECT content, progress, created_at FROM logs WHERE job_id = ? ORDER BY created_at",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job_logs_after(job_id: str, after_id: int) -> List[Dict[str, Any]]:
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT id, content, progress, created_at FROM logs WHERE job_id = ? AND id > ? ORDER BY id",
            (job_id, after_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_job(job_id: str) -> Dict:
    conn = _get_db()
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return {"success": True}
