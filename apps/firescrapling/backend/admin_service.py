"""Admin platform-wide queries (gated by ADMIN_SECRET at the route layer)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from db import _get_db


def admin_get_stats() -> Dict[str, Any]:
    """Platform-wide counts for the admin overview."""
    conn = _get_db()
    try:
        total_users = int(conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] or 0)
        usage = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS ok,
                   AVG(response_time_ms) AS avg_ms
            FROM api_usage
            WHERE created_at >= datetime('now', '-30 days')
            """
        ).fetchone()
        total_req = int(usage["total"] or 0)
        ok = int(usage["ok"] or 0)
        job_counts = {
            r["status"]: int(r["c"] or 0)
            for r in conn.execute("SELECT status, COUNT(*) AS c FROM jobs GROUP BY status").fetchall()
        }
        active_jobs = job_counts.get("running", 0) + job_counts.get("queued", 0)
        failed_jobs = job_counts.get("failed", 0)
        return {
            "total_users": total_users,
            "total_requests_30d": total_req,
            "success_rate": round(100.0 * ok / total_req, 1) if total_req else 100.0,
            "active_jobs": active_jobs,
            "failed_jobs": failed_jobs,
            "avg_latency_ms": int(usage["avg_ms"] or 0),
            "jobs_by_status": job_counts,
        }
    finally:
        conn.close()


def admin_get_health() -> Dict[str, Any]:
    """Lightweight admin health probe (also used to validate the admin token)."""
    conn = _get_db()
    try:
        conn.execute("SELECT 1")
        users = int(conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] or 0)
        active_sessions = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM sessions WHERE expires_at > datetime('now')"
            ).fetchone()["c"]
            or 0
        )
        return {"db": "ok", "users": users, "active_sessions": active_sessions}
    finally:
        conn.close()


def admin_list_users(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Paginated user list with key/job/usage aggregates, optional email search."""
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    conn = _get_db()
    try:
        where = ""
        params: List[Any] = []
        if search and search.strip():
            where = "WHERE u.email LIKE ?"
            params.append(f"%{search.strip().lower()}%")

        total = int(
            conn.execute(f"SELECT COUNT(*) AS c FROM users u {where}", params).fetchone()["c"] or 0
        )
        rows = conn.execute(
            f"""
            SELECT u.id, u.email, u.full_name, u.created_at,
                   (SELECT COUNT(*) FROM api_keys k WHERE k.user_id = u.id) AS key_count,
                   (SELECT COUNT(*) FROM jobs j WHERE j.user_id = u.id) AS job_count,
                   (SELECT COUNT(*) FROM api_usage a
                    WHERE a.user_id = u.id
                      AND a.created_at >= datetime('now', '-30 days')) AS request_count_30d
            FROM users u
            {where}
            ORDER BY u.created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        users = [
            {
                "id": r["id"],
                "email": r["email"],
                "full_name": r["full_name"],
                "created_at": r["created_at"],
                "key_count": int(r["key_count"] or 0),
                "job_count": int(r["job_count"] or 0),
                "request_count_30d": int(r["request_count_30d"] or 0),
            }
            for r in rows
        ]
        return {"users": users, "total": total, "limit": limit, "offset": offset}
    finally:
        conn.close()


def admin_delete_user(user_id: str) -> bool:
    """Delete a user; CASCADE removes keys, sessions, usage, and their jobs."""
    conn = _get_db()
    try:
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def admin_list_jobs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Paginated platform-wide job list with optional status/type filters."""
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    conn = _get_db()
    try:
        clauses: List[str] = []
        params: List[Any] = []
        if status and status.strip():
            clauses.append("j.status = ?")
            params.append(status.strip())
        if job_type and job_type.strip():
            clauses.append("j.type = ?")
            params.append(job_type.strip())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        total = int(
            conn.execute(f"SELECT COUNT(*) AS c FROM jobs j {where}", params).fetchone()["c"] or 0
        )
        rows = conn.execute(
            f"""
            SELECT j.id, j.type, j.status, j.url, j.created_at, j.finished_at,
                   j.error_message, j.progress, u.email AS user_email
            FROM jobs j
            LEFT JOIN users u ON u.id = j.user_id
            {where}
            ORDER BY j.created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        jobs = [
            {
                "id": r["id"],
                "user_email": r["user_email"],
                "type": r["type"],
                "status": r["status"],
                "url": r["url"],
                "created_at": r["created_at"],
                "finished_at": r["finished_at"],
                "error_message": r["error_message"],
                "progress": r["progress"] or 0,
            }
            for r in rows
        ]
        return {"jobs": jobs, "total": total, "limit": limit, "offset": offset}
    finally:
        conn.close()


def admin_delete_job(job_id: str) -> bool:
    conn = _get_db()
    try:
        cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
