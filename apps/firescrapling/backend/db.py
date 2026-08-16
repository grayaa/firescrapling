"""Database paths, sqlite/Postgres connections, schema init, and SQLAlchemy Core."""
from __future__ import annotations

import logging
import os
import re
import sqlite3
from typing import Any, Iterable, Mapping, Optional, Sequence, Union

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.engine import Connection as SAConnection
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError as SAIntegrityError

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

# Shared metadata for Alembic / Core table defs.
metadata = MetaData()

_engine: Optional[Engine] = None

Params = Union[Sequence[Any], Mapping[str, Any], None]


def default_database_url() -> str:
    """sqlite:/// absolute path; override with DATABASE_URL (Postgres in compose profile)."""
    env = (os.environ.get("DATABASE_URL") or "").strip()
    if env:
        return env
    # Three slashes + absolute path for Windows/Unix sqlite URLs.
    return f"sqlite:///{DB_PATH.replace(os.sep, '/')}"


def is_postgres_url(url: Optional[str] = None) -> bool:
    u = (url or default_database_url()).strip().lower()
    return u.startswith("postgresql") or u.startswith("postgres")


def get_engine(*, url: Optional[str] = None, force_new: bool = False) -> Engine:
    """Lazy SQLAlchemy engine (Core). Used by Alembic and the Postgres service adapter."""
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


# ---------------------------------------------------------------------------
# Postgres adapter — sqlite3-shaped API over SQLAlchemy (qmark + datetime())
# ---------------------------------------------------------------------------

class DbRow:
    """sqlite3.Row-compatible mapping (key + index access, dict())."""

    __slots__ = ("_data", "_keys")

    def __init__(self, mapping: Mapping[str, Any]) -> None:
        self._data = dict(mapping)
        self._keys = list(self._data.keys())

    def keys(self) -> Iterable[str]:
        return self._data.keys()

    def __getitem__(self, key: Union[str, int]) -> Any:
        if isinstance(key, int):
            return self._data[self._keys[key]]
        return self._data[key]

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __iter__(self):
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class DbCursor:
    """Minimal cursor: fetchone/fetchall/rowcount after execute()."""

    def __init__(self, result: Any) -> None:
        self._result = result
        rc = getattr(result, "rowcount", None)
        self.rowcount = int(rc) if rc is not None and rc >= 0 else 0

    def fetchone(self) -> Optional[DbRow]:
        row = self._result.fetchone()
        if row is None:
            return None
        return DbRow(row._mapping)

    def fetchall(self) -> list[DbRow]:
        return [DbRow(r._mapping) for r in self._result.fetchall()]


_RE_DT_NOW = re.compile(r"datetime\('now'\)", re.IGNORECASE)
_RE_DT_NOW_LIT = re.compile(r"datetime\('now',\s*'([^']+)'\)", re.IGNORECASE)
_RE_DT_NOW_PARAM = re.compile(r"datetime\('now',\s*\?\)", re.IGNORECASE)
_RE_DT_REPLACE = re.compile(
    r"datetime\(replace\(([^,]+),\s*'T',\s*' '\)\)", re.IGNORECASE
)
_RE_DATE = re.compile(r"\bdate\(([^)]+)\)", re.IGNORECASE)
_RE_BEGIN_IMM = re.compile(r"^\s*BEGIN\s+IMMEDIATE\s*$", re.IGNORECASE)


def _norm_interval(modifier: str) -> str:
    """SQLite datetime modifiers ('+72 hours', '-30 days') → Postgres interval text."""
    return modifier.strip().lstrip("+").strip()


def _rewrite_sql_postgres(sql: str) -> str:
    """Translate the sqlite-shaped SQL this codebase emits into Postgres."""
    if _RE_BEGIN_IMM.match(sql.strip()):
        # SA connections autobegin; exclusive lock is best-effort via the txn.
        return "SELECT 1 WHERE false"
    out = sql
    out = _RE_DT_REPLACE.sub(
        r"CAST(replace(replace(\1, 'T', ' '), 'Z', '') AS TIMESTAMP)", out
    )
    out = _RE_DT_NOW_LIT.sub(
        lambda m: f"(CURRENT_TIMESTAMP + INTERVAL '{_norm_interval(m.group(1))}')", out
    )
    out = _RE_DT_NOW_PARAM.sub("(CURRENT_TIMESTAMP + CAST(? AS interval))", out)
    out = _RE_DT_NOW.sub("CURRENT_TIMESTAMP", out)
    out = _RE_DATE.sub(r"(CAST(\1 AS timestamptz)::date)", out)
    # Timestamp columns are TEXT in the schema; cast before comparing to timestamptz.
    out = re.sub(
        r"\b(expires_at|created_at|finished_at|last_used|last_used_at|updated_at|current_period_end)"
        r"\s*(>=|<=|>|<)\s*",
        r"\1::timestamptz \2 ",
        out,
        flags=re.IGNORECASE,
    )
    return out


def _qmark_to_binds(sql: str, params: Params) -> tuple[str, dict[str, Any]]:
    if params is None:
        return sql, {}
    if isinstance(params, Mapping):
        return sql, dict(params)
    binds: dict[str, Any] = {}
    idx = 0

    def _repl(_: re.Match[str]) -> str:
        nonlocal idx
        key = f"p{idx}"
        binds[key] = params[idx]  # type: ignore[index]
        idx += 1
        return f":{key}"

    return re.sub(r"\?", _repl, sql), binds


class PgConnection:
    """sqlite3.Connection lookalike backed by SQLAlchemy for Postgres."""

    def __init__(self, sa_conn: SAConnection) -> None:
        self._conn = sa_conn

    def execute(self, sql: str, params: Params = None) -> DbCursor:
        rewritten = _rewrite_sql_postgres(sql)
        named_sql, binds = _qmark_to_binds(rewritten, params)
        # Normalize interval modifiers passed as bound strings ('+72 hours').
        for k, v in list(binds.items()):
            if isinstance(v, str) and re.fullmatch(
                r"[+-]?\d+\s+(seconds|minutes|hours|days|months|years)",
                v.strip(),
                flags=re.IGNORECASE,
            ):
                binds[k] = _norm_interval(v)
        try:
            result = self._conn.execute(text(named_sql), binds)
        except SAIntegrityError as e:
            # Call sites catch sqlite3.IntegrityError (auth/jobs idempotency).
            raise sqlite3.IntegrityError(str(e.orig if getattr(e, "orig", None) else e)) from e
        return DbCursor(result)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def _connect_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Job threads and request handlers each hold their own connection; wait for a
    # writer to finish rather than failing immediately with "database is locked".
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _connect() -> Union[sqlite3.Connection, PgConnection]:
    """Open a DB connection. Never runs DDL — call init_db() / alembic at startup.

    SQLite: native sqlite3 (local/tests).
    Postgres: SQLAlchemy adapter that accepts the existing qmark / datetime() SQL.
    """
    if is_postgres_url():
        return PgConnection(get_engine().connect())
    return _connect_sqlite()


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
    if is_postgres_url():
        logger.info(
            "DATABASE_URL is Postgres — skipping sqlite bootstrap; "
            "expect `alembic upgrade head` (compose entrypoint runs it)"
        )
        from settings import get_settings

        get_settings().validate_startup()
        eng = get_engine(force_new=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return

    conn = _connect_sqlite()
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
