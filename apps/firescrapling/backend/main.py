import base64
import logging
import os
import sqlite3
import threading
import uuid
import json
import time
import secrets
from typing import Generator, List, Dict, Any, Optional, Set

from dotenv import load_dotenv
from passlib.context import CryptContext

from webhook_delivery import deliver_webhook

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

logger = logging.getLogger(__name__)

# Configuration (paths relative to this file so local and Docker cwd both work)
_BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_BACKEND_ROOT, "..", "..", ".."))
# Project root .env first, then optional backend-local override, then process env / cwd
load_dotenv(os.path.join(_REPO_ROOT, ".env"))
load_dotenv(os.path.join(_BACKEND_ROOT, ".env"))
load_dotenv()
DATA_DIR = os.path.join(_BACKEND_ROOT, "data/db")
CACHE_DIR = os.path.join(_BACKEND_ROOT, "data/cache")
DB_PATH = os.path.join(DATA_DIR, "firescrapling.db")

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    
    # Tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            key_value TEXT UNIQUE NOT NULL,
            name TEXT,
            last_used TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            key_id TEXT,
            endpoint TEXT NOT NULL,
            status_code INTEGER,
            response_time_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (key_id) REFERENCES api_keys(id) ON DELETE SET NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            markdown TEXT,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            content TEXT NOT NULL,
            progress INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    _migrate_jobs_and_idempotency(conn)
    conn.commit()
    return conn


def _migrate_jobs_and_idempotency(conn: sqlite3.Connection) -> None:
    for col, decl in (
        ("progress", "INTEGER DEFAULT 0"),
        ("error_message", "TEXT"),
        ("webhook_url", "TEXT"),
        ("webhook_secret", "TEXT"),
    ):
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {decl}")
        except sqlite3.OperationalError:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            key_id TEXT,
            idempotency_key TEXT NOT NULL,
            job_id TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, idempotency_key, endpoint)
        )
    """)

def _add_log(conn, job_id, content, progress=None):
    conn.execute("INSERT INTO logs (job_id, content, progress) VALUES (?, ?, ?)", (job_id, content, progress))
    conn.commit()


def _extract_structured_via_openrouter(schema: Dict[str, Any], markdown: Optional[str], html_content: str) -> Dict[str, Any]:
    """JSON extraction via OpenRouter (OpenAI-compatible API). Requires OPENROUTER_API_KEY."""
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "Structured extraction requires OPENROUTER_API_KEY in the environment (e.g. apps/firescrapling/backend/.env)."
        )
    from openai import OpenAI

    default_headers = {}
    referer = (os.environ.get("OPENROUTER_HTTP_REFERER") or "").strip()
    if referer:
        default_headers["HTTP-Referer"] = referer
    title = (os.environ.get("OPENROUTER_APP_TITLE") or "").strip()
    if title:
        default_headers["X-Title"] = title

    client_kwargs: Dict[str, Any] = {
        "base_url": (os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip(),
        "api_key": api_key,
    }
    if default_headers:
        client_kwargs["default_headers"] = default_headers
    client = OpenAI(**client_kwargs)
    model = (os.environ.get("OPENROUTER_MODEL") or "google/gemini-2.0-flash-001").strip()
    body = (markdown or "")[:15000] if markdown else ""
    if not body.strip():
        body = html_content[:15000]
    prompt = (
        "Extract structured data from the following web content according to this JSON schema description. "
        "Respond with a single JSON object only, no markdown fences.\n\n"
        f"Schema (guidance): {json.dumps(schema)}\n\nContent:\n{body}"
    )
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    raw = completion.choices[0].message.content
    if not raw:
        raise RuntimeError("OpenRouter returned empty content")
    return json.loads(raw)


# --- Auth Functions ---

def register_user(email: str, password: str, full_name: str = None) -> Dict:
    conn = _get_db()
    try:
        user_id = str(uuid.uuid4())
        hashed_pw = pwd_context.hash(password)
        conn.execute(
            "INSERT INTO users (id, email, hashed_password, full_name) VALUES (?, ?, ?, ?)",
            (user_id, email.lower(), hashed_pw, full_name)
        )
        conn.commit()
        return {"success": True, "user": {"id": user_id, "email": email, "full_name": full_name}}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Email already registered"}
    finally:
        conn.close()

def login_user(email: str, password: str) -> Dict:
    conn = _get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    conn.close()
    
    if user and pwd_context.verify(password, user["hashed_password"]):
        return {
            "success": True, 
            "user": {"id": user["id"], "email": user["email"], "full_name": user["full_name"]}
        }
    return {"success": False, "error": "Invalid email or password"}

# --- API Key Management ---

def create_api_key(user_id: str, name: str) -> Dict:
    conn = _get_db()
    try:
        key_id = str(uuid.uuid4())
        key_value = f"fs_{secrets.token_urlsafe(32)}"
        conn.execute(
            "INSERT INTO api_keys (id, user_id, key_value, name) VALUES (?, ?, ?, ?)",
            (key_id, user_id, key_value, name)
        )
        conn.commit()
        return {"success": True, "key": {"id": key_id, "value": key_value, "name": name}}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def get_api_keys(user_id: str) -> List[Dict]:
    conn = _get_db()
    rows = conn.execute("SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_api_keys_masked(user_id: str) -> List[Dict[str, Any]]:
    """API key list with key_value masked (never expose full secret after creation)."""
    out: List[Dict[str, Any]] = []
    for r in get_api_keys(user_id):
        d = dict(r)
        d["key_preview"] = mask_key_value(d.pop("key_value", "") or "")
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
    rows = conn.execute("""
        SELECT u.*, k.name as key_name 
        FROM api_usage u 
        LEFT JOIN api_keys k ON u.key_id = k.id 
        WHERE u.user_id = ? 
        ORDER BY u.created_at DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mask_key_value(key_value: str) -> str:
    if not key_value or len(key_value) <= 10:
        return "fs_****"
    return f"{key_value[:6]}…{key_value[-4:]}"


def resolve_api_key(raw_key: str) -> Optional[Dict[str, str]]:
    if not raw_key or not raw_key.strip():
        return None
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id FROM api_keys WHERE key_value = ?",
            (raw_key.strip(),),
        ).fetchone()
        if not row:
            return None
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


def create_session_token(user_id: str, ttl_hours: int = 72) -> str:
    conn = _get_db()
    try:
        token = secrets.token_urlsafe(48)
        sid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO sessions (id, user_id, token, expires_at) VALUES (?, ?, ?, datetime('now', ?))",
            (sid, user_id, token, f"+{int(ttl_hours)} hours"),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def resolve_session_token(token: str) -> Optional[str]:
    if not token or not token.strip():
        return None
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (token.strip(),),
        ).fetchone()
        return row["user_id"] if row else None
    finally:
        conn.close()


def revoke_session_token(token: str) -> None:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token.strip(),))
        conn.commit()
    finally:
        conn.close()


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
        row = conn.execute("SELECT * FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()
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


def _update_job_progress(conn: sqlite3.Connection, job_id: str, progress: int) -> None:
    p = min(100, max(0, int(progress)))
    conn.execute("UPDATE jobs SET progress = ? WHERE id = ?", (p, job_id))


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


# --- Scraping Functions ---

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
) -> Generator:
    logger.info("scrape start job context url=%s user=%s formats=%s onlyMain=%s", url, user_id, formats, onlyMainContent)
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

        if use_playwright:
            want_shot = "screenshot" in formats
            html_content, png_bytes = run_playwright_page(url, actions if actions else None, want_shot)
        else:
            cached = read_response_cache(url, onlyMainContent, fmt_key)
            if cached and cached.get("html"):
                html_content = cached["html"]
                final_url = cached.get("final_url", url)
                http_status = int(cached.get("status", 200))
                log_msg = "Loaded from cache"
                _add_log(conn, job_id, log_msg, 45)
                _update_job_progress(conn, job_id, 45)
                conn.commit()
                yield {"type": "status", "content": log_msg, "progress": 45}
            else:
                response = fetch_with_retries(url, timeout=30)
                html_content = response.html_content or ""
                final_url = getattr(response, "url", url) or url
                http_status = int(getattr(response, "status", 200) or 200)
                try:
                    write_response_cache(
                        url,
                        onlyMainContent,
                        fmt_key,
                        {"html": html_content, "final_url": final_url, "status": http_status},
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

        record_api_usage(user_id, key_id, usage_endpoint, http_status, int((time.time() - start_time) * 1000))

        conn.commit()
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
        record_api_usage(user_id, key_id, usage_endpoint, int(getattr(e, "status", 500) or 500), int((time.time() - start_time) * 1000))
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
) -> Generator:
    logger.info("crawl start url=%s limit=%s depth=%s ignore_subdomains=%s", url, limit, maxDepth, ignore_subdomains)
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
                record_api_usage(user_id, key_id, usage_endpoint, 200, int((time.time() - start_time) * 1000))
                conn.commit()
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
        ):
            pass
    except Exception:
        logger.exception("background scrape failed job=%s", job_id)


def spawn_crawl_thread(
    job_id: str,
    url: str,
    user_id: Optional[str],
    key_id: Optional[str],
    limit: int,
    max_depth: int,
    ignore_subdomains: bool,
) -> None:
    threading.Thread(
        target=run_crawl_background,
        args=(job_id, url, user_id, key_id, limit, max_depth, ignore_subdomains),
        daemon=True,
        name=f"crawl-{job_id[:8]}",
    ).start()


def spawn_scrape_thread(
    job_id: str,
    url: str,
    user_id: Optional[str],
    key_id: Optional[str],
    formats: List[str],
    only_main_content: bool,
    actions: Optional[List[Dict]],
    schema: Optional[Dict],
) -> None:
    threading.Thread(
        target=run_scrape_background,
        args=(job_id, url, user_id, key_id, formats, only_main_content, actions, schema),
        daemon=True,
        name=f"scrape-{job_id[:8]}",
    ).start()


def map_domain(
    url: str,
    user_id: str = None,
    key_id: str = None,
    search: str = None,
    ignoreSubdomains: bool = False,
    usage_endpoint: str = "/v1/map",
) -> Dict:
    logger.info("map_domain url=%s ignoreSubdomains=%s", url, ignoreSubdomains)
    start_time = time.time()
    try:
        seed = normalize_http_url(url)
        response = fetch_with_retries(seed, timeout=15)
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

def get_job_history(user_id: str = None, limit: int = 50) -> List[Dict]:
    conn = _get_db()
    rows = conn.execute("SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall() if user_id else conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_job_results(job_id: str) -> List[Dict]:
    conn = _get_db()
    rows = conn.execute("SELECT * FROM results WHERE job_id = ? ORDER BY created_at", (job_id,)).fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        meta = json.loads(d.pop('metadata_json', '{}'))
        d['metadata'] = meta
        if 'structured_data' in meta: d['data'] = meta['structured_data']
        res.append(d)
    return res

def get_job_logs(job_id: str) -> List[Dict]:
    conn = _get_db()
    rows = conn.execute("SELECT content, progress, created_at FROM logs WHERE job_id = ? ORDER BY created_at", (job_id,)).fetchall()
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
