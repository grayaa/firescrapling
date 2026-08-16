"""Shared pytest fixtures for the FireScrapling backend test suite."""
from __future__ import annotations

import http.server
import os
import socketserver
import sys
import threading
from typing import Generator
from unittest.mock import MagicMock

import pytest

# Make the backend package importable when pytest is run from the backend dir or repo root.
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from tests.fixtures_html import HTML_INDEX, HTML_PAGE2, HTML_RELATIVE, HTML_ROBOTS


# ---------------------------------------------------------------------------
# Fixture HTTP server — no network needed
# ---------------------------------------------------------------------------

class _FixtureHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index"):
            body, ct = HTML_INDEX.encode("utf-8"), "text/html; charset=utf-8"
        elif path == "/page2":
            body, ct = HTML_PAGE2.encode("utf-8"), "text/html; charset=utf-8"
        elif path == "/relative":
            body, ct = HTML_RELATIVE.encode("utf-8"), "text/html; charset=utf-8"
        elif path == "/robots.txt":
            body, ct = HTML_ROBOTS.encode("utf-8"), "text/plain"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def fixture_server() -> Generator[str, None, None]:
    """Start a local HTTP server once for the test session. Yields the base URL."""
    with socketserver.TCPServer(("127.0.0.1", 0), _FixtureHandler) as httpd:
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        yield f"http://127.0.0.1:{port}"
        httpd.shutdown()
        t.join(timeout=2)


# ---------------------------------------------------------------------------
# Hermetic defaults — no live provider calls unless a test opts in
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_live_providers(monkeypatch: pytest.MonkeyPatch):
    """No test may reach a paid provider unless it opts in explicitly."""
    for var in ("SCRAPFLY_API_KEY", "SCRAPE_API_KEY", "SCRAPE_DO_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    # SSRF stays closed by default; tests that need localhost/fixture URLs opt in.
    monkeypatch.delenv("API_ALLOW_PRIVATE_URLS", raising=False)
    monkeypatch.setenv("FETCH_PROVIDER", "local")
    monkeypatch.setenv("FETCH_ESCALATE", "false")
    from settings import clear_settings_cache

    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture()
def stub_paid_fetcher(monkeypatch: pytest.MonkeyPatch):
    """
    Opt-in ladder testing: FETCH_ESCALATE=true + a recorder paid fetcher.
    Never uses a real API key. Yields the MagicMock fetcher.
    """
    from fetch_provider import FetchResult

    monkeypatch.setenv("FETCH_ESCALATE", "true")
    monkeypatch.setenv("SCRAPE_API_KEY", "test-stub-key-not-real")
    monkeypatch.setenv("FETCH_PROVIDER", "scrapedo")
    from settings import clear_settings_cache

    clear_settings_cache()

    recorder = MagicMock()
    recorder.fetch.return_value = FetchResult(
        html_content="<html><body>" + ("ok content " * 40) + "</body></html>",
        url="https://example.com/",
        status=200,
    )

    def _paid(_ctx=None):
        return recorder

    monkeypatch.setattr("fetch_strategy._paid_fetcher", _paid)
    yield recorder
    clear_settings_cache()


# ---------------------------------------------------------------------------
# Isolated SQLite DB — fresh file per test
# ---------------------------------------------------------------------------

@pytest.fixture()
def isolated_db(tmp_path: "pytest.TempPathFactory", monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """Patch db.DB_PATH / main.DB_PATH to a temp file and initialise the schema."""
    import db
    import main as core
    from settings import clear_settings_cache

    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr(core, "DB_PATH", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db.reset_engine()
    # Threads only — Redis not required for unit tests.
    monkeypatch.setenv("QUEUE_ENABLED", "false")
    clear_settings_cache()
    core.init_db()
    yield db_path
    db.reset_engine()
    clear_settings_cache()


# ---------------------------------------------------------------------------
# TestClient — isolated DB + fresh rate limiter per test
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """FastAPI TestClient with an isolated DB and a reset rate limiter."""
    import api_auth
    from api_auth import _SlidingWindow
    from settings import clear_settings_cache

    # Reset the in-process rate limiter so tests can't interfere with each other.
    monkeypatch.setattr(api_auth, "_rate_limiter", _SlidingWindow())
    # Tests register many users; production defaults to closed after first account.
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    clear_settings_cache()

    from fastapi.testclient import TestClient
    from api_server import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Convenience: a fully registered + keyed client
# ---------------------------------------------------------------------------

@pytest.fixture()
def authed(client):
    """
    Yields (client, api_key, session_token) with a registered test user.

    The returned client has the API key pre-set as a default header so
    authenticated /v1/scrape|crawl|map calls work without extra headers.
    """
    r = client.post("/v1/auth/register", json={
        "email": "fixture@example.com",
        "password": "FixturePass99!",
    })
    assert r.status_code == 200, r.text

    r = client.post("/v1/auth/login", json={
        "email": "fixture@example.com",
        "password": "FixturePass99!",
    })
    assert r.status_code == 200, r.text
    session_token = r.json()["session_token"]

    r = client.post(
        "/v1/keys",
        json={"name": "ci-test-key"},
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert r.status_code == 200, r.text
    api_key = r.json()["key"]["value"]

    client.headers.update({"X-API-Key": api_key})
    return client, api_key, session_token
