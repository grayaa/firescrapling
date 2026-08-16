"""
Core scraping utilities: main-content extraction, retries, cache, crawl BFS, map helpers.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import random
import re
import threading
import time
import urllib.parse
import urllib.robotparser
from collections import defaultdict, deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Any, Dict, List, Optional, Set, Tuple

import tldextract
import trafilatura
from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger = logging.getLogger(__name__)

_BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
_CACHE_ROOT = os.path.join(_BACKEND_ROOT, "data", "cache")

FETCH_MAX_RETRIES = 3
FETCH_BACKOFF_BASE = 0.5
CRAWL_DELAY_BASE = 0.4
CRAWL_DELAY_JITTER = 0.35
MAX_HTML_STORE_BYTES = 5_000_000
CACHE_TTL_SECONDS = int(os.environ.get("SCRAPE_CACHE_TTL", "3600"))


def crawl_concurrency_caps() -> Tuple[int, int]:
    """(global, per_host) worker caps from env."""
    try:
        global_cap = max(1, int(os.environ.get("CRAWL_GLOBAL_CONCURRENCY") or "4"))
    except ValueError:
        global_cap = 4
    try:
        per_host = max(1, int(os.environ.get("CRAWL_PER_HOST_CONCURRENCY") or "2"))
    except ValueError:
        per_host = 2
    return global_cap, min(per_host, global_cap)


def _host_key(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


class ScrapeHTTPError(Exception):
    def __init__(self, status: int, url: str, message: str = ""):
        self.status = status
        self.url = url
        super().__init__(message or f"HTTP {status} for {url}")


def _ensure_cache_dir() -> None:
    os.makedirs(_CACHE_ROOT, exist_ok=True)


def cache_key(url: str, only_main: bool, format_fingerprint: str) -> str:
    raw = f"{url}|{only_main}|{format_fingerprint}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_path(key: str) -> str:
    return os.path.join(_CACHE_ROOT, key[:2], f"{key[2:]}.json")


def read_response_cache(url: str, only_main: bool, format_fingerprint: str) -> Optional[Dict[str, Any]]:
    _ensure_cache_dir()
    key = cache_key(url, only_main, format_fingerprint)
    path = cache_path(key)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("ts", 0) > CACHE_TTL_SECONDS:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def write_response_cache(url: str, only_main: bool, format_fingerprint: str, payload: Dict[str, Any]) -> None:
    _ensure_cache_dir()
    key = cache_key(url, only_main, format_fingerprint)
    path = cache_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = {"ts": time.time(), "url": url, **payload}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f)


def fetch_with_retries(
    url: str,
    timeout: int = 30,
    max_retries: int = FETCH_MAX_RETRIES,
    *,
    render_js: Optional[bool] = None,
    asp: Optional[bool] = None,
    proxy_pool: Optional[str] = None,
    country: Optional[str] = None,
    ctx: Any = None,
) -> Any:
    """Fetch via credit-aware strategy (or single-shot); retry 5xx/429 within the final attempt."""
    from fetch_provider import FetchError
    from fetch_strategy import fetch_with_strategy

    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            response = fetch_with_strategy(
                url,
                timeout=timeout,
                render_js=render_js,
                asp=asp,
                proxy_pool=proxy_pool,
                country=country,
                ctx=ctx,
            )
            status = int(getattr(response, "status", None) or 200)
            if status >= 500 and attempt < max_retries - 1:
                time.sleep(FETCH_BACKOFF_BASE * (2**attempt) + random.uniform(0, 0.2))
                continue
            if status == 429 and attempt < max_retries - 1:
                time.sleep(FETCH_BACKOFF_BASE * (2 ** (attempt + 1)))
                continue
            if status >= 400:
                raise ScrapeHTTPError(status, url)
            return response
        except ScrapeHTTPError:
            raise
        except FetchError as e:
            last_err = e
            if attempt < max_retries - 1 and e.status >= 500:
                time.sleep(FETCH_BACKOFF_BASE * (2**attempt) + random.uniform(0, 0.2))
                continue
            raise ScrapeHTTPError(e.status, url, str(e)) from e
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(FETCH_BACKOFF_BASE * (2**attempt) + random.uniform(0, 0.2))
            else:
                raise
    if last_err:
        raise last_err
    raise RuntimeError("fetch_with_retries: unreachable")


def html_to_markdown(html: str, page_url: str, only_main_content: bool) -> str:
    """Main-content pipeline via trafilatura when only_main_content; else full-page markdownify."""
    if only_main_content:
        try:
            extracted = trafilatura.extract(
                html,
                url=page_url,
                output_format="markdown",
                include_comments=False,
                include_tables=True,
                favor_precision=True,
            )
            if extracted and extracted.strip():
                return extracted.strip()
        except Exception as e:
            logger.warning("trafilatura extract failed for %s: %s", page_url, e)
    return md(html, heading_style="ATX")


def normalize_http_url(url: str) -> str:
    """Strip fragment; normalize for deduplication."""
    url = urllib.parse.urldefrag(url)[0]
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https"):
        return url
    netloc = p.netloc.lower()
    path = p.path or "/"
    if not path.endswith("/") and path != "" and "." not in os.path.basename(path):
        pass
    return urllib.parse.urlunparse((p.scheme, netloc, path, p.params, p.query, ""))


def registered_domain_parts(url: str) -> Tuple[str, str]:
    ext = tldextract.extract(url)
    if not ext.suffix:
        return (ext.domain, "")
    return (ext.domain, ext.suffix)


def same_site(seed_url: str, candidate_url: str, ignore_subdomains: bool) -> bool:
    """Whether candidate is in scope: same host only vs same eTLD+1."""
    try:
        s = urllib.parse.urlparse(seed_url)
        c = urllib.parse.urlparse(candidate_url)
        if c.scheme not in ("http", "https"):
            return False
        host_s = s.netloc.split(":")[0].lower()
        host_c = c.netloc.split(":")[0].lower()
        if ignore_subdomains:
            return host_s == host_c
        d1 = registered_domain_parts(seed_url)
        d2 = registered_domain_parts(candidate_url)
        return d1 == d2 and d1[0] != ""
    except Exception:
        return False


def extract_links_from_html(html: str, base_url: str) -> List[str]:
    """Absolute http(s) links from HTML."""
    out: List[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        abs_u = urllib.parse.urljoin(base_url, href)
        if abs_u.startswith("http://") or abs_u.startswith("https://"):
            out.append(normalize_http_url(abs_u))
    return out


def extract_image_urls_from_html(html: str, base_url: str) -> List[str]:
    """Absolute http(s) image URLs from img[src] and srcset."""
    out: List[str] = []
    seen: Set[str] = set()
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and str(src).strip():
            abs_u = urllib.parse.urljoin(base_url, str(src).strip())
            if abs_u.startswith("http://") or abs_u.startswith("https://"):
                nu = normalize_http_url(abs_u)
                if nu not in seen:
                    seen.add(nu)
                    out.append(nu)
        srcset = img.get("srcset")
        if not srcset:
            continue
        for part in str(srcset).split(","):
            chunk = part.strip().split()
            if not chunk:
                continue
            u = chunk[0].strip()
            if u:
                abs_u = urllib.parse.urljoin(base_url, u)
                if abs_u.startswith("http://") or abs_u.startswith("https://"):
                    nu = normalize_http_url(abs_u)
                    if nu not in seen:
                        seen.add(nu)
                        out.append(nu)
    return out


def try_fetch_sitemap_urls(seed_url: str, timeout: int = 15) -> List[str]:
    """Optional sitemap.xml discovery (best-effort)."""
    p = urllib.parse.urlparse(seed_url)
    if not p.scheme or not p.netloc:
        return []
    sm = urllib.parse.urlunparse((p.scheme, p.netloc, "/sitemap.xml", "", "", ""))
    try:
        r = fetch_with_retries(sm, timeout=timeout, max_retries=2)
        if getattr(r, "status", 200) >= 400:
            return []
        text = r.html_content or ""
        if not text.strip():
            return []
        urls = re.findall(r"<loc[^>]*>\s*([^<\s]+)\s*</loc>", text, re.I)
        return [normalize_http_url(u.strip()) for u in urls if u.startswith("http")]
    except ScrapeHTTPError:
        return []
    except Exception as e:
        logger.debug("sitemap fetch skipped: %s", e)
        return []


class RobotsCache:
    def __init__(self) -> None:
        self._parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}

    def can_fetch(self, url: str, user_agent: str = "FireScraplingBot") -> bool:
        p = urllib.parse.urlparse(url)
        if not p.scheme or not p.netloc:
            return True
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._parsers:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = urllib.parse.urljoin(base + "/", "robots.txt")
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                pass
            self._parsers[base] = rp
        try:
            return self._parsers[base].can_fetch(user_agent, url)
        except Exception:
            return True


_robots = RobotsCache()


def run_playwright_page(
    url: str,
    actions: Optional[List[Dict[str, Any]]],
    want_screenshot: bool,
    timeout_ms: int = 60000,
) -> Tuple[str, Optional[bytes]]:
    """Return (html_content, png_bytes or None)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if actions:
                for act in actions:
                    t = (act.get("type") or "").lower()
                    if t == "wait":
                        ms = min(int(act.get("milliseconds", 500)), 15000)
                        page.wait_for_timeout(ms)
                    elif t == "click" and act.get("selector"):
                        page.click(act["selector"], timeout=10000)
                    elif t == "scroll":
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                    elif t == "screenshot":
                        pass
            html = page.content()
            png: Optional[bytes] = None
            if want_screenshot:
                png = page.screenshot(full_page=True, type="png")
            return html, png
        finally:
            browser.close()


def classify_error(exc: Exception) -> str:
    if isinstance(exc, ScrapeHTTPError):
        return f"http_error:{exc.status}"
    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "403" in msg or "forbidden" in msg:
        return "blocked"
    return "error"


def extract_title_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    t = soup.title
    if t and t.string:
        return t.string.strip()
    return "No Title"


def crawl_bfs_iter(
    seed_url: str,
    limit: int,
    max_depth: int,
    ignore_subdomains: bool,
    *,
    render_js: Optional[bool] = None,
    asp: Optional[bool] = None,
    proxy_pool: Optional[str] = None,
    country: Optional[str] = None,
    ctx: Any = None,
):
    """
    Concurrent BFS crawl generator. Yields:
      ("page", {url, html, title, markdown, depth, index, total_limit})
      ("done", {count, errors})

    Caps via CRAWL_GLOBAL_CONCURRENCY (default 4) and CRAWL_PER_HOST_CONCURRENCY
    (default 2). Still honors robots.txt and per-request politeness delay.
    """
    errors: List[str] = []
    queue: deque[Tuple[str, int]] = deque([(normalize_http_url(seed_url), 0)])
    seen: Set[str] = set()
    queued: Set[str] = {normalize_http_url(seed_url)}
    count = 0
    seed_norm = normalize_http_url(seed_url)
    global_cap, per_host_cap = crawl_concurrency_caps()
    host_sems: Dict[str, threading.Semaphore] = defaultdict(lambda: threading.Semaphore(per_host_cap))
    host_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

    def _fetch_one(current: str, depth: int) -> Tuple[str, int, Optional[Dict[str, Any]], Optional[str]]:
        host = _host_key(current)
        sem = host_sems[host]
        sem.acquire()
        try:
            # Serialize delay per host so politeness holds under concurrency.
            with host_locks[host]:
                time.sleep(CRAWL_DELAY_BASE + random.uniform(0, CRAWL_DELAY_JITTER))
            response = fetch_with_retries(
                current,
                timeout=25,
                render_js=render_js,
                asp=asp,
                proxy_pool=proxy_pool,
                country=country,
                ctx=ctx,
            )
            html = response.html_content or ""
            if len(html) > MAX_HTML_STORE_BYTES:
                html = html[:MAX_HTML_STORE_BYTES]
            title = extract_title_from_html(html)
            md_text = html_to_markdown(html, current, only_main_content=True)
            return current, depth, {
                "url": current,
                "html": html,
                "title": title,
                "markdown": md_text,
                "depth": depth,
            }, None
        except Exception as e:
            return current, depth, None, f"{current}: {e}"
        finally:
            sem.release()

    in_flight: Dict[Future, Tuple[str, int]] = {}

    with ThreadPoolExecutor(max_workers=global_cap) as pool:
        while (queue or in_flight) and count < limit:
            while queue and len(in_flight) < global_cap and count + len(in_flight) < limit:
                current, depth = queue.popleft()
                if current in seen:
                    continue
                seen.add(current)
                if depth > max_depth:
                    continue
                if not _robots.can_fetch(current):
                    errors.append(f"robots_disallow:{current}")
                    continue
                fut = pool.submit(_fetch_one, current, depth)
                in_flight[fut] = (current, depth)

            if not in_flight:
                break

            done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                in_flight.pop(fut, None)
                try:
                    current, depth, page, err = fut.result()
                except Exception as e:
                    errors.append(str(e))
                    logger.warning("crawl worker failed: %s", e)
                    continue
                if err:
                    errors.append(err)
                    logger.warning("crawl skip %s", err)
                    continue
                if not page or count >= limit:
                    continue
                count += 1
                page["index"] = count
                page["total_limit"] = limit
                yield ("page", page)

                if depth < max_depth and count < limit:
                    for link in extract_links_from_html(page.get("html") or "", current):
                        if not same_site(seed_norm, link, ignore_subdomains):
                            continue
                        nu = normalize_http_url(link)
                        if nu not in seen and nu not in queued:
                            queued.add(nu)
                            queue.append((nu, depth + 1))

    yield ("done", {"count": count, "errors": errors})
