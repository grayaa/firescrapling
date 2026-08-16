"""RQ worker entrypoints — importable string paths for enqueue."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _bootstrap() -> None:
    """Ensure schema + logging exist in the worker process (no FastAPI lifespan)."""
    import main as core

    core.configure_logging()
    core.init_db()


def run_scrape_job(
    job_id: str,
    url: str,
    user_id: Optional[str],
    key_id: Optional[str],
    formats: List[str],
    only_main_content: bool,
    actions: Optional[List[Dict]],
    schema: Optional[Dict],
    render_js: Optional[bool] = None,
    asp: Optional[bool] = None,
    proxy_pool: Optional[str] = None,
    country: Optional[str] = None,
) -> None:
    _bootstrap()
    import main as core

    try:
        for _ in core.scrape_page_streaming(
            url=url,
            user_id=user_id,
            key_id=key_id,
            formats=formats,
            onlyMainContent=only_main_content,
            actions=actions,
            schema=schema,
            existing_job_id=job_id,
            render_js=render_js,
            asp=asp,
            proxy_pool=proxy_pool,
            country=country,
        ):
            pass
    except Exception:
        logger.exception("RQ scrape failed job=%s", job_id)
        raise


def run_crawl_job(
    job_id: str,
    url: str,
    user_id: Optional[str],
    key_id: Optional[str],
    limit: int,
    max_depth: int,
    ignore_subdomains: bool,
    render_js: Optional[bool] = None,
    asp: Optional[bool] = None,
    proxy_pool: Optional[str] = None,
    country: Optional[str] = None,
) -> None:
    _bootstrap()
    import main as core

    try:
        for _ in core.crawl_site_streaming(
            url=url,
            user_id=user_id,
            key_id=key_id,
            limit=limit,
            maxDepth=max_depth,
            ignore_subdomains=ignore_subdomains,
            existing_job_id=job_id,
            render_js=render_js,
            asp=asp,
            proxy_pool=proxy_pool,
            country=country,
        ):
            pass
    except Exception:
        logger.exception("RQ crawl failed job=%s", job_id)
        raise


def run_webhook_delivery(
    url: str,
    secret: str,
    event: str,
    payload: Dict[str, Any],
    idempotency_key: str,
) -> bool:
    from webhook_delivery import deliver_webhook

    return deliver_webhook(url, secret, event, payload, idempotency_key)
