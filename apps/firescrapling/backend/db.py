"""Database paths, sqlite connections, schema init, and SQLAlchemy Core skeleton."""
from __future__ import annotations

import logging
import os
import sqlite3
from typing import Any, Optional

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_BACKEND_ROOT, "..", "..", ".."))
# Project root .env first, then optional backend-local override, then process env / cwd
load_dotenv(os.path.join(_REPO_ROOT, ".env"))
load_dotenv(os.path.join(_BACKEND_ROOT, ".env"))
load_dotenv()

DATA_DIR = os.path.join(_BACKEND_ROOT, "data/db")
CACHE_DIR = os.path.join(_BACKEND_ROOT, "data/cache")
DB_PATH = os.path.join(DATA_DIR, "firescrapling.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# Shared metadata for Alembic / future Core table defs (queries still use sqlite3 today).
metadata = MetaData()

_engine: Optional[Engine] = None


def default_database_url() -> str:
    """sqlite:/// absolute path; override with DATABASE_URL (Postgres in compose profile)."""
    env = (os.environ.get("DATABASE_URL") or "").strip()
    if env:
        return env
    # Three slashes + absolute path for Windows/Unix sqlite URLs.
    return f"sqlite:///{DB_PATH.replace(os.sep, '/')}"


def get_engine(*, url: Optional[str] = None, force_new: bool = False) -> Engine:
    """Lazy SQLAlchemy engine (Core). Used by Alembic and future query migration."""
    global _engine
    if _engine is not None and not force_new and url is None:
        return _engine
    if force_new and _engine is not None and url is None:
        _engine.dispose()
        _engine = None
    db_url = url or default_database_url()
    connect_args: dict[str, Any] = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    eng = create_engine(db_url, future=True, connect_args=connect_args)
    if db_url.startswith("sqlite"):

        @event.listens_for(eng, "connect")
        def _sqlite_pragma(dbapi_conn, _connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

    if url is None:
        _engine = eng
    return eng


def reset_engine() -> None:
    """Drop cached engine (tests that change DB_PATH / DATABASE_URL)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def _connect() -> sqlite3.Connection:
    """Open a DB connection with WAL + busy-timeout. Never runs DDL — call init_db() at startup.

    Still sqlite3-based for the service layer; SQLAlchemy Core is the migration path.
    When DATABASE_URL points at Postgres, callers should use get_engine() instead —
    local/tests keep the default sqlite file path.
    """
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url and not url.startswith("sqlite"):
        # Bridge: expose a sqlite3-like surface only for sqlite. Postgres uses Core.
        raise RuntimeError(
            "sqlite3 _connect() is only for sqlite. Set DATABASE_URL to sqlite:///… "
            "or migrate the caller to SQLAlchemy Core (get_engine())."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Job threads and request handlers each hold their own connection; wait for a
    # writer to finish rather than failing immediately with "database is locked".
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


# Alias kept for backward-compat (health_ready in api_server.py etc.)
_get_db = _connect


def _migrate_jobs_and_idempotency(conn: sqlite3.Connection) -> None:
    """Legacy in-place alters — also captured in Alembic revision 001. Kept for init_db bootstrap."""
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
    conn.execute(
        """
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
        """
    )


def _migrate_api_key_hashing(conn: sqlite3.Connection) -> None:
    """Add key_hash / key_hint; hash any leftover plaintext key_value rows."""
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(api_keys)").fetchall()}
    if "key_hash" not in cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN key_hash TEXT")
    if "key_hint" not in cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN key_hint TEXT")
    # Late import avoids circular import with keys_service at module load.
    from keys_service import hash_api_key, key_hint_from_value

    rows = conn.execute("SELECT id, key_value, key_hash, key_hint FROM api_keys").fetchall()
    for row in rows:
        kv = (row["key_value"] or "").strip()
        if row["key_hash"]:
            continue
        if kv.startswith("fs_") and len(kv) > 16:
            # Legacy plaintext — hash and clear.
            h = hash_api_key(kv)
            hint = key_hint_from_value(kv)
            conn.execute(
                "UPDATE api_keys SET key_hash = ?, key_hint = ?, key_value = ? WHERE id = ?",
                (h, hint, h, row["id"]),
            )
        elif len(kv) == 64 and all(c in "0123456789abcdef" for c in kv.lower()):
            # Already a sha256 hex stored in key_value without key_hash filled.
            conn.execute(
                "UPDATE api_keys SET key_hash = ?, key_hint = COALESCE(key_hint, ?) WHERE id = ?",
                (kv, "fs_****", row["id"]),
            )
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)"
        )
    except sqlite3.OperationalError:
        pass


def init_db() -> None:
    """Create schema and run migrations. Call once at process startup.

    Prefer `alembic upgrade head` in deployed environments; this bootstrap keeps
    local/tests working without a separate migration step.
    """
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url and not url.startswith("sqlite"):
        # Service layer still uses sqlite3 helpers; Postgres is Alembic + Core.
        logger.info(
            "DATABASE_URL is non-sqlite — skipping sqlite bootstrap; "
            "run `alembic upgrade head` for schema"
        )
        from settings import get_settings

        get_settings().validate_startup()
        eng = get_engine(force_new=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return

    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                key_value TEXT UNIQUE NOT NULL,
                key_hash TEXT,
                key_hint TEXT,
                name TEXT,
                last_used TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
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
            """
        )
        conn.execute(
            """
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
            """
        )
        conn.execute(
            """
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
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                content TEXT NOT NULL,
                progress INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        _migrate_jobs_and_idempotency(conn)
        _migrate_api_key_hashing(conn)
        # BYOK + savings tables (also in alembic 001; created here for SQLite bootstrap).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_credentials (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                label TEXT,
                encrypted_key BLOB NOT NULL,
                key_hint TEXT NOT NULL,
                proxy_pool TEXT,
                residential_pool TEXT,
                country TEXT,
                status TEXT NOT NULL DEFAULT 'unverified',
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                UNIQUE(user_id, provider),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fetch_events (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                job_id TEXT,
                url TEXT,
                domain TEXT NOT NULL,
                provider TEXT,
                source TEXT,
                final_tier TEXT,
                attempts_json TEXT,
                profile_hit INTEGER DEFAULT 0,
                baseline_cost REAL,
                actual_cost REAL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fetch_events_user_created ON fetch_events(user_id, created_at)"
        )
        from billing import ensure_subscriptions_table

        ensure_subscriptions_table(conn)
        conn.commit()
    finally:
        conn.close()
    # Fail closed for BYOK encryption key (after schema so health can still boot in tests
    # that set BYOK_ENABLED=false).
    from settings import get_settings

    get_settings().validate_startup()
    # Touch SQLAlchemy engine so misconfigured DATABASE_URL fails early.
    try:
        eng = get_engine(force_new=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        logger.debug("SQLAlchemy engine probe skipped/failed", exc_info=True)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with a timestamped format. Safe to call multiple times."""
    import logging as _logging

    lvl = getattr(_logging, level.upper(), _logging.INFO)
    _logging.basicConfig(
        level=lvl,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )
