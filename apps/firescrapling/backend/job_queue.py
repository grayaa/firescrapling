"""Redis RQ job queue — scrapes, crawls, and webhook delivery."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

QUEUE_JOBS = "firescrapling-jobs"
QUEUE_WEBHOOKS = "firescrapling-webhooks"

JobKind = Literal["scrape", "crawl"]


def _redis_conn():
    from redis import Redis
    from settings import get_settings

    return Redis.from_url(get_settings().redis_url)


def queue_available() -> bool:
    from settings import get_settings

    if not get_settings().queue_enabled:
        return False
    try:
        return bool(_redis_conn().ping())
    except Exception:
        return False


def get_jobs_queue():
    from rq import Queue

    return Queue(QUEUE_JOBS, connection=_redis_conn())


def get_webhooks_queue():
    from rq import Queue

    return Queue(QUEUE_WEBHOOKS, connection=_redis_conn())


def enqueue_scrape_job(
    job_id: str,
    url: str,
    user_id: Optional[str],
    key_id: Optional[str],
    formats: List[str],
    only_main_content: bool,
    actions: Optional[List[Dict]],
    schema: Optional[Dict],
    *,
    render_js: Optional[bool] = None,
    asp: Optional[bool] = None,
    proxy_pool: Optional[str] = None,
    country: Optional[str] = None,
) -> None:
    from settings import get_settings

    if get_settings().queue_enabled and queue_available():
        get_jobs_queue().enqueue(
            "job_tasks.run_scrape_job",
            job_id,
            url,
            user_id,
            key_id,
            formats,
            only_main_content,
            actions,
            schema,
            render_js,
            asp,
            proxy_pool,
            country,
            job_id=f"scrape-{job_id}",
            job_timeout="30m",
            result_ttl=86400,
            failure_ttl=86400,
        )
        return
    # Fallback: in-process thread
    import main as core

    core.spawn_scrape_thread_local(
        job_id, url, user_id, key_id, formats, only_main_content, actions, schema,
        render_js=render_js, asp=asp, proxy_pool=proxy_pool, country=country,
    )


def enqueue_crawl_job(
    job_id: str,
    url: str,
    user_id: Optional[str],
    key_id: Optional[str],
    limit: int,
    max_depth: int,
    ignore_subdomains: bool,
    *,
    render_js: Optional[bool] = None,
    asp: Optional[bool] = None,
    proxy_pool: Optional[str] = None,
    country: Optional[str] = None,
) -> None:
    from settings import get_settings

    if get_settings().queue_enabled and queue_available():
        get_jobs_queue().enqueue(
            "job_tasks.run_crawl_job",
            job_id,
            url,
            user_id,
            key_id,
            limit,
            max_depth,
            ignore_subdomains,
            render_js,
            asp,
            proxy_pool,
            country,
            job_id=f"crawl-{job_id}",
            job_timeout="2h",
            result_ttl=86400,
            failure_ttl=86400,
        )
        return
    import main as core

    core.spawn_crawl_thread_local(
        job_id, url, user_id, key_id, limit, max_depth, ignore_subdomains,
        render_js=render_js, asp=asp, proxy_pool=proxy_pool, country=country,
    )


def dispatch_job(kind: JobKind, payload: Dict[str, Any]) -> None:
    """Single entrypoint for scrape/crawl enqueue (RQ or in-process thread)."""
    if kind == "scrape":
        enqueue_scrape_job(
            payload["job_id"],
            payload["url"],
            payload.get("user_id"),
            payload.get("key_id"),
            payload.get("formats") or ["markdown"],
            bool(payload.get("only_main_content", True)),
            payload.get("actions"),
            payload.get("schema"),
            render_js=payload.get("render_js"),
            asp=payload.get("asp"),
            proxy_pool=payload.get("proxy_pool"),
            country=payload.get("country"),
        )
        return
    if kind == "crawl":
        enqueue_crawl_job(
            payload["job_id"],
            payload["url"],
            payload.get("user_id"),
            payload.get("key_id"),
            int(payload.get("limit") or 100),
            int(payload.get("max_depth") or 2),
            bool(payload.get("ignore_subdomains", False)),
            render_js=payload.get("render_js"),
            asp=payload.get("asp"),
            proxy_pool=payload.get("proxy_pool"),
            country=payload.get("country"),
        )
        return
    raise ValueError(f"unknown job kind: {kind!r}")


def enqueue_webhook(
    url: str,
    secret: str,
    event: str,
    payload: Dict[str, Any],
    idempotency_key: str,
) -> None:
    from settings import get_settings

    if get_settings().queue_enabled and queue_available():
        get_webhooks_queue().enqueue(
            "job_tasks.run_webhook_delivery",
            url,
            secret,
            event,
            payload,
            idempotency_key,
            job_timeout="5m",
            result_ttl=3600,
            failure_ttl=86400,
        )
        return
    from webhook_delivery import deliver_webhook

    deliver_webhook(url, secret, event, payload, idempotency_key)


def recover_orphaned_jobs() -> int:
    """Re-enqueue jobs left in queued/running after a process crash. Returns count."""
    import main as core

    if not queue_available():
        return 0
    conn = core._get_db()
    recovered = 0
    try:
        rows = conn.execute(
            """
            SELECT id, type, url, user_id, status
            FROM jobs
            WHERE status IN ('queued', 'running')
            ORDER BY created_at ASC
            LIMIT 100
            """
        ).fetchall()
        for row in rows:
            jid = row["id"]
            # Mark back to queued and re-dispatch with minimal args — running scrapes
            # without stored options fall back to defaults.
            conn.execute(
                "UPDATE jobs SET status = 'queued', progress = 0 WHERE id = ?",
                (jid,),
            )
            conn.commit()
            if row["type"] == "crawl":
                dispatch_job(
                    "crawl",
                    {
                        "job_id": jid,
                        "url": row["url"],
                        "user_id": row["user_id"],
                        "key_id": None,
                        "limit": 100,
                        "max_depth": 2,
                        "ignore_subdomains": False,
                    },
                )
            else:
                dispatch_job(
                    "scrape",
                    {
                        "job_id": jid,
                        "url": row["url"],
                        "user_id": row["user_id"],
                        "key_id": None,
                        "formats": ["markdown"],
                        "only_main_content": True,
                        "actions": None,
                        "schema": None,
                    },
                )
            recovered += 1
            logger.info("recovered orphaned job %s (%s)", jid, row["type"])
    except Exception:
        logger.exception("job recovery failed")
    finally:
        conn.close()
    return recovered
