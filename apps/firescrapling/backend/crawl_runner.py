"""Scrape/crawl streaming runners, background threads, and map."""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
import uuid
from typing import Any, Dict, Generator, List, Optional, Set

from scraping_engine import (
    ScrapeHTTPError,
    classify_error,
    crawl_bfs_iter,
    extract_image_urls_from_html,
    extract_links_from_html,
    extract_title_from_html,
    fetch_with_retries,
    html_to_markdown,
    normalize_http_url,
    read_response_cache,
    run_playwright_page,
    same_site,
    try_fetch_sitemap_urls,
    write_response_cache,
)

from db import _get_db
from extraction import _extract_structured_via_openrouter
from jobs_service import _add_log, _notify_job_webhook, _update_job_progress
from keys_service import record_api_usage

logger = logging.getLogger(__name__)


def scrape_page_streaming(
    url: str,
    user_id: str = None,
    key_id: str = None,
    formats: List[str] = ["markdown"],
    onlyMainContent: bool = True,
    actions: List[Dict] = None,
    schema: Dict = None,
    existing_job_id: Optional[str] = None,
    webhook_url: Optional[str] = None,
    webhook_secret: Optional[str] = None,
    usage_endpoint: str = "/v1/scrape",
    render_js: Optional[bool] = None,
    asp: Optional[bool] = None,
    proxy_pool: Optional[str] = None,
    country: Optional[str] = None,
) -> Generator:
    from provider_credentials import build_fetch_context, touch_credential_used

    fetch_ctx = build_fetch_context(user_id)
    logger.info(
        "scrape start url=%s user=%s source=%s provider=%s formats=%s",
        url,
        user_id,
        fetch_ctx.source,
        fetch_ctx.provider,
        formats,
    )
    conn = _get_db()
    start_time = time.time()
    if existing_job_id:
        job_id = existing_job_id
        conn.execute(
            "UPDATE jobs SET status = 'running', progress = 0, error_message = NULL WHERE id = ?",
            (job_id,),
        )
    else:
        job_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO jobs (id, user_id, type, url, status, progress, webhook_url, webhook_secret) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, user_id, "scrape", url, "running", 0, webhook_url, webhook_secret),
        )
    conn.commit()
    actions = actions or []
    formats = list(formats) if formats else ["markdown"]
    fmt_key = "|".join(sorted(formats))

    try:
        log_msg = "Initializing FireScrapling engine..."
        _add_log(conn, job_id, log_msg, 10)
        _update_job_progress(conn, job_id, 10)
        conn.commit()
        yield {"type": "status", "content": log_msg, "progress": 10}

        use_playwright = bool(actions) or ("screenshot" in formats)
        if actions:
            log_msg = f"Running {len(actions)} browser actions (Playwright)..."
            _add_log(conn, job_id, log_msg, 20)
            _update_job_progress(conn, job_id, 20)
            conn.commit()
            yield {"type": "status", "content": log_msg, "progress": 20}

        log_msg = f"Fetching {url}..."
        _add_log(conn, job_id, log_msg, 40)
        _update_job_progress(conn, job_id, 40)
        conn.commit()
        yield {"type": "status", "content": log_msg, "progress": 40}

        html_content = ""
        final_url = url
        http_status = 200
        png_bytes: Optional[bytes] = None
        fetch_meta: Optional[Dict[str, Any]] = None

        if use_playwright:
            want_shot = "screenshot" in formats
            html_content, png_bytes = run_playwright_page(url, actions if actions else None, want_shot)
        else:
            cached = read_response_cache(url, onlyMainContent, fmt_key)
            if cached and cached.get("html"):
                html_content = cached["html"]
                final_url = cached.get("final_url", url)
                http_status = int(cached.get("status", 200))
                if isinstance(cached.get("fetch"), dict):
                    fetch_meta = cached["fetch"]
                log_msg = "Loaded from cache"
                _add_log(conn, job_id, log_msg, 45)
                _update_job_progress(conn, job_id, 45)
                conn.commit()
                yield {"type": "status", "content": log_msg, "progress": 45}
            else:
                response = fetch_with_retries(
                    url,
                    timeout=30,
                    render_js=render_js,
                    asp=asp,
                    proxy_pool=proxy_pool,
                    country=country,
                    ctx=fetch_ctx,
                )
                html_content = response.html_content or ""
                final_url = getattr(response, "url", url) or url
                http_status = int(getattr(response, "status", 200) or 200)
                fetch_meta = {
                    "tier": getattr(response, "fetch_tier", None) or "unknown",
                    "escalated": bool(getattr(response, "escalated", False)),
                    "attempts": list(getattr(response, "attempts", None) or []),
                    "source": fetch_ctx.source,
                    "provider": fetch_ctx.provider,
                    "profile_hit": bool(getattr(response, "profile_hit", False)),
                    "domain": getattr(response, "domain", "") or "",
                }
                if fetch_ctx.credential_id:
                    try:
                        touch_credential_used(fetch_ctx.credential_id)
                    except Exception:
                        pass
                try:
                    from fetch_events import record_fetch_event

                    record_fetch_event(
                        user_id=user_id,
                        job_id=job_id,
                        url=final_url,
                        provider=fetch_ctx.provider,
                        source=fetch_ctx.source,
                        final_tier=str(fetch_meta["tier"]),
                        attempts=list(fetch_meta["attempts"]),
                        profile_hit=bool(fetch_meta["profile_hit"]),
                    )
                except Exception:
                    logger.exception("fetch_event persist failed")
                try:
                    write_response_cache(
                        url,
                        onlyMainContent,
                        fmt_key,
                        {
                            "html": html_content,
                            "final_url": final_url,
                            "status": http_status,
                            "fetch": fetch_meta,
                        },
                    )
                except OSError as e:
                    logger.warning("cache write failed: %s", e)

        if len(html_content) > 5_000_000:
            html_content = html_content[:5_000_000]

        try:
            title = extract_title_from_html(html_content)
        except Exception:
            title = "No Title"

        results_data: Dict[str, Any] = {
            "metadata": {
                "status": http_status,
                "url": final_url,
                "error_class": None,
                "onlyMainContent": onlyMainContent,
            }
        }
        if fetch_meta:
            results_data["metadata"]["fetch"] = fetch_meta

        if "html" in formats:
            results_data["html"] = html_content
        if "raw_content" in formats:
            results_data["raw_content"] = html_content
        if "markdown" in formats:
            results_data["markdown"] = html_to_markdown(html_content, final_url, onlyMainContent)
        if "screenshot" in formats and png_bytes:
            results_data["screenshot"] = base64.b64encode(png_bytes).decode("ascii")
        if "links" in formats:
            try:
                raw_links = extract_links_from_html(html_content, final_url)
                seen_l: Set[str] = set()
                links_out: List[str] = []
                for u in raw_links:
                    if u not in seen_l:
                        seen_l.add(u)
                        links_out.append(u)
                results_data["links"] = links_out
            except Exception:
                results_data["links"] = []
        if "images" in formats:
            try:
                results_data["images"] = extract_image_urls_from_html(html_content, final_url)
            except Exception:
                results_data["images"] = []

        structured_data = None
        if schema:
            log_msg = "Structured extraction (OpenRouter)..."
            _add_log(conn, job_id, log_msg, 70)
            _update_job_progress(conn, job_id, 70)
            conn.commit()
            yield {"type": "status", "content": log_msg, "progress": 70}
            structured_data = _extract_structured_via_openrouter(
                schema,
                results_data.get("markdown"),
                html_content,
            )
            results_data["llm_extraction"] = structured_data

        conn.execute(
            "INSERT INTO results (id, job_id, url, title, markdown, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), job_id, final_url, title, results_data.get("markdown"), json.dumps(results_data)),
        )

        conn.execute(
            "UPDATE jobs SET status='completed', finished_at=CURRENT_TIMESTAMP, progress=100 WHERE id=?",
            (job_id,),
        )

        # Commit before touching the DB through any other connection: SQLite allows a
        # single writer, and record_api_usage/_notify_job_webhook open their own.
        conn.commit()
        record_api_usage(user_id, key_id, usage_endpoint, http_status, int((time.time() - start_time) * 1000))
        _notify_job_webhook(job_id, "scrape.completed", {"url": final_url, "title": title})
        yield {
            "type": "result",
            "data": {
                "job_id": job_id,
                "url": final_url,
                "title": title,
                "markdown": results_data.get("markdown"),
                "metadata": results_data["metadata"],
                "data": structured_data,
                "raw": results_data,
            },
        }
        yield {"type": "status", "content": "Scrape completed successfully.", "progress": 100}

    except ScrapeHTTPError as e:
        err = f"[{classify_error(e)}] {e}"
        conn.execute(
            "UPDATE jobs SET status='failed', error_message=?, finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (err[:5000], job_id),
        )
        conn.commit()
        record_api_usage(
            user_id, key_id, usage_endpoint, int(getattr(e, "status", 500) or 500), int((time.time() - start_time) * 1000)
        )
        logger.warning("scrape http error job=%s %s", job_id, err)
        _notify_job_webhook(job_id, "scrape.failed", {"error": err})
        yield {"type": "error", "content": err}
    except Exception as e:
        err = f"[{classify_error(e)}] {e}"
        conn.execute(
            "UPDATE jobs SET status='failed', error_message=?, finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (err[:5000], job_id),
        )
        conn.commit()
        record_api_usage(user_id, key_id, usage_endpoint, 500, int((time.time() - start_time) * 1000))
        logger.exception("scrape failed job=%s", job_id)
        _notify_job_webhook(job_id, "scrape.failed", {"error": err})
        yield {"type": "error", "content": err}
    finally:
        conn.close()
        yield {"type": "done"}


def crawl_site_streaming(
    url: str,
    user_id: str = None,
    key_id: str = None,
    limit: int = 100,
    maxDepth: int = 2,
    ignore_subdomains: bool = False,
    existing_job_id: Optional[str] = None,
    webhook_url: Optional[str] = None,
    webhook_secret: Optional[str] = None,
    usage_endpoint: str = "/v1/crawl",
    render_js: Optional[bool] = None,
    asp: Optional[bool] = None,
    proxy_pool: Optional[str] = None,
    country: Optional[str] = None,
) -> Generator:
    from provider_credentials import build_fetch_context

    fetch_ctx = build_fetch_context(user_id)
    logger.info(
        "crawl start url=%s limit=%s depth=%s source=%s provider=%s",
        url,
        limit,
        maxDepth,
        fetch_ctx.source,
        fetch_ctx.provider,
    )
    conn = _get_db()
    start_time = time.time()
    if existing_job_id:
        job_id = existing_job_id
        conn.execute(
            "UPDATE jobs SET status = 'running', progress = 0, error_message = NULL WHERE id = ?",
            (job_id,),
        )
    else:
        job_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO jobs (id, user_id, type, url, status, progress, webhook_url, webhook_secret) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, user_id, "crawl", url, "running", 0, webhook_url, webhook_secret),
        )
    conn.commit()
    last_err: Optional[str] = None
    try:
        yield {"type": "job", "id": job_id}
        log_msg = f"Starting crawl for {url} (limit={limit}, maxDepth={maxDepth})..."
        _add_log(conn, job_id, log_msg, 10)
        _update_job_progress(conn, job_id, 10)
        conn.commit()
        yield {"type": "status", "content": log_msg, "progress": 10}

        for ev, payload in crawl_bfs_iter(
            seed_url=url,
            limit=min(max(1, limit), 500),
            max_depth=max(0, maxDepth),
            ignore_subdomains=ignore_subdomains,
            render_js=render_js,
            asp=asp,
            proxy_pool=proxy_pool,
            country=country,
            ctx=fetch_ctx,
        ):
            if ev == "page":
                idx = payload["index"]
                prog = min(95, 10 + int(85 * idx / max(payload["total_limit"], 1)))
                rid = str(uuid.uuid4())
                meta = {
                    "depth": payload["depth"],
                    "index": idx,
                    "metadata": {"status": 200, "url": payload["url"]},
                }
                conn.execute(
                    "INSERT INTO results (id, job_id, url, title, markdown, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (rid, job_id, payload["url"], payload["title"], payload["markdown"], json.dumps(meta)),
                )
                _update_job_progress(conn, job_id, prog)
                conn.commit()
                yield {
                    "type": "status",
                    "content": f"Crawled {idx}/{payload['total_limit']}: {payload['url']}",
                    "progress": prog,
                }
            elif ev == "done":
                if payload.get("errors"):
                    _add_log(conn, job_id, "Some URLs skipped: " + "; ".join(payload["errors"][:5]), 92)
                    conn.commit()
                conn.execute(
                    "UPDATE jobs SET status='completed', finished_at=CURRENT_TIMESTAMP, progress=100 WHERE id=?",
                    (job_id,),
                )
                conn.commit()
                record_api_usage(user_id, key_id, usage_endpoint, 200, int((time.time() - start_time) * 1000))
                _notify_job_webhook(
                    job_id,
                    "crawl.completed",
                    {"url": url, "pages": payload.get("count", 0)},
                )
                yield {"type": "status", "content": f"Crawl finished ({payload['count']} pages).", "progress": 100}
                yield {"type": "done", "total": payload["count"]}
    except Exception as e:
        last_err = str(e)
        conn.execute(
            "UPDATE jobs SET status='failed', error_message=?, finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (last_err[:5000], job_id),
        )
        conn.commit()
        record_api_usage(user_id, key_id, usage_endpoint, 500, int((time.time() - start_time) * 1000))
        logger.exception("crawl failed job=%s", job_id)
        _notify_job_webhook(job_id, "crawl.failed", {"error": last_err})
        yield {"type": "error", "content": last_err}
    finally:
        conn.close()


def run_crawl_background(
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
    try:
        for _ in crawl_site_streaming(
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
        logger.exception("background crawl failed job=%s", job_id)


def run_scrape_background(
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
    try:
        for _ in scrape_page_streaming(
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
        logger.exception("background scrape failed job=%s", job_id)


def spawn_crawl_thread_local(
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
    threading.Thread(
        target=run_crawl_background,
        args=(job_id, url, user_id, key_id, limit, max_depth, ignore_subdomains, render_js, asp, proxy_pool, country),
        daemon=True,
        name=f"crawl-{job_id[:8]}",
    ).start()


def spawn_scrape_thread_local(
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
    threading.Thread(
        target=run_scrape_background,
        args=(job_id, url, user_id, key_id, formats, only_main_content, actions, schema, render_js, asp, proxy_pool, country),
        daemon=True,
        name=f"scrape-{job_id[:8]}",
    ).start()


def spawn_crawl_thread(
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
    from job_queue import dispatch_job

    dispatch_job(
        "crawl",
        {
            "job_id": job_id,
            "url": url,
            "user_id": user_id,
            "key_id": key_id,
            "limit": limit,
            "max_depth": max_depth,
            "ignore_subdomains": ignore_subdomains,
            "render_js": render_js,
            "asp": asp,
            "proxy_pool": proxy_pool,
            "country": country,
        },
    )


def spawn_scrape_thread(
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
    from job_queue import dispatch_job

    dispatch_job(
        "scrape",
        {
            "job_id": job_id,
            "url": url,
            "user_id": user_id,
            "key_id": key_id,
            "formats": formats,
            "only_main_content": only_main_content,
            "actions": actions,
            "schema": schema,
            "render_js": render_js,
            "asp": asp,
            "proxy_pool": proxy_pool,
            "country": country,
        },
    )


def map_domain(
    url: str,
    user_id: str = None,
    key_id: str = None,
    search: str = None,
    ignoreSubdomains: bool = False,
    usage_endpoint: str = "/v1/map",
) -> Dict:
    from provider_credentials import build_fetch_context

    fetch_ctx = build_fetch_context(user_id)
    logger.info("map_domain url=%s ignoreSubdomains=%s source=%s", url, ignoreSubdomains, fetch_ctx.source)
    start_time = time.time()
    try:
        seed = normalize_http_url(url)
        response = fetch_with_retries(seed, timeout=15, ctx=fetch_ctx)
        html = response.html_content or ""
        raw_links = extract_links_from_html(html, seed)
        seen: Set[str] = set()
        unique_links: List[str] = []
        for link in raw_links:
            if not same_site(seed, link, ignoreSubdomains):
                continue
            nu = normalize_http_url(link)
            if nu not in seen:
                seen.add(nu)
                unique_links.append(nu)
        for su in try_fetch_sitemap_urls(seed):
            if same_site(seed, su, ignoreSubdomains) and su not in seen:
                seen.add(su)
                unique_links.append(su)
        if search:
            q = search.lower()
            unique_links = [u for u in unique_links if q in u.lower()]

        record_api_usage(user_id, key_id, usage_endpoint, 200, int((time.time() - start_time) * 1000))

        return {"success": True, "links": sorted(unique_links)}
    except Exception as e:
        logger.warning("map_domain failed: %s", e)
        record_api_usage(user_id, key_id, usage_endpoint, 500, int((time.time() - start_time) * 1000))
        return {"success": False, "error": str(e)}
