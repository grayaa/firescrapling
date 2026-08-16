"""
FastAPI integration tests via TestClient.

Covers:
- Auth-required endpoints reject unauthenticated requests.
- Register + login + key creation flow.
- Tenant isolation: user A cannot read user B's job.
- Idempotency key replay returns the same job_id.
- Rate-limit 429 with correct headers.
- Regression: bcrypt-direct registration/login round-trip (passlib bug).
- Regression: scrape completes without 'database is locked' (SQLite writer bug).
"""
from __future__ import annotations

import time

import pytest


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_ready(client) -> None:
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


# ---------------------------------------------------------------------------
# Auth-required endpoints — unauthenticated must get 401
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path,body", [
    ("post", "/v1/scrape", {"url": "http://example.com"}),
    ("post", "/v1/crawl", {"url": "http://example.com"}),
    ("post", "/v1/map",   {"url": "http://example.com"}),
])
def test_auth_required(client, method: str, path: str, body: dict) -> None:
    r = getattr(client, method)(path, json=body)
    assert r.status_code == 401, f"{path} should require auth, got {r.status_code}: {r.text}"


def test_keys_list_requires_session(client) -> None:
    r = client.get("/v1/keys")
    assert r.status_code == 401


def test_usage_summary_requires_session(client) -> None:
    r = client.get("/v1/usage/summary")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Register + login + key lifecycle
# ---------------------------------------------------------------------------

def test_register_and_login(client) -> None:
    r = client.post("/v1/auth/register", json={
        "email": "newuser@example.com",
        "password": "NewPass99!",
    })
    assert r.status_code == 200
    assert r.json()["success"] is True

    r = client.post("/v1/auth/login", json={
        "email": "newuser@example.com",
        "password": "NewPass99!",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "session_token" in data


def test_login_wrong_password_returns_401(client) -> None:
    client.post("/v1/auth/register", json={
        "email": "wrongpw@example.com",
        "password": "CorrectPass1!",
    })
    r = client.post("/v1/auth/login", json={
        "email": "wrongpw@example.com",
        "password": "WrongPass99!",
    })
    assert r.status_code == 401


def test_create_and_list_keys(client) -> None:
    client.post("/v1/auth/register", json={"email": "ktest@example.com", "password": "KeyPass99!"})
    lr = client.post("/v1/auth/login", json={"email": "ktest@example.com", "password": "KeyPass99!"})
    token = lr.json()["session_token"]
    hdrs = {"Authorization": f"Bearer {token}"}

    cr = client.post("/v1/keys", json={"name": "my-key"}, headers=hdrs)
    assert cr.status_code == 200
    key_value = cr.json()["key"]["value"]
    assert key_value.startswith("fs_")

    lr2 = client.get("/v1/keys", headers=hdrs)
    assert lr2.status_code == 200
    keys = lr2.json()["keys"]
    assert any(k["name"] == "my-key" for k in keys)


# ---------------------------------------------------------------------------
# Error envelope shape
# ---------------------------------------------------------------------------

def test_error_envelope_shape(client) -> None:
    r = client.post("/v1/scrape", json={"url": "http://example.com"})
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
    err = body["error"]
    assert "code" in err
    assert "message" in err
    assert "request_id" in err


# ---------------------------------------------------------------------------
# Regression: passlib bug — registration + login must succeed (bcrypt direct)
# ---------------------------------------------------------------------------

def test_passlib_regression_via_api(client) -> None:
    """Registration used to 500 when passlib drove bcrypt ≥ 4.1."""
    r = client.post("/v1/auth/register", json={
        "email": "passlib_reg@test.com",
        "password": "RegressPass1!",
        "full_name": "Regression User",
    })
    assert r.status_code == 200, f"register failed: {r.text}"

    r = client.post("/v1/auth/login", json={
        "email": "passlib_reg@test.com",
        "password": "RegressPass1!",
    })
    assert r.status_code == 200, f"login failed: {r.text}"
    assert r.json()["success"] is True


# ---------------------------------------------------------------------------
# Regression: database is locked — scrape must complete cleanly
# ---------------------------------------------------------------------------

def test_db_locked_regression(client, fixture_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scrape used to fail with 'database is locked' when record_api_usage opened
    a second writer while the job transaction was still open. The fix commits before
    calling record_api_usage / _notify_job_webhook."""
    # Allow the SSRF guard to pass for localhost so we can use the fixture server.
    monkeypatch.setenv("API_ALLOW_PRIVATE_URLS", "1")
    _, api_key = _register_and_key(client, "dblocked@example.com", "DbLocked1!")

    r = client.post(
        "/v1/scrape",
        json={"url": fixture_server + "/"},
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200, f"scrape failed: {r.text}"
    data = r.json()
    assert data["success"] is True
    assert data["data"]["markdown"]  # got actual content back


# ---------------------------------------------------------------------------
# Tenant isolation: user A cannot read user B's job
# ---------------------------------------------------------------------------

def _register_and_key(client, email: str, password: str) -> tuple[str, str]:
    """Helper: register user, login, create key; returns (session_token, api_key)."""
    client.post("/v1/auth/register", json={"email": email, "password": password})
    lr = client.post("/v1/auth/login", json={"email": email, "password": password})
    token = lr.json()["session_token"]
    kr = client.post("/v1/keys", json={"name": "key"},
                     headers={"Authorization": f"Bearer {token}"})
    return token, kr.json()["key"]["value"]


def test_tenant_isolation_crawl_job(client, fixture_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """User A starts a crawl; user B must get 404 when asking for that job."""
    monkeypatch.setenv("API_ALLOW_PRIVATE_URLS", "1")
    _, key_a = _register_and_key(client, "user_a@example.com", "PassA99!")
    _, key_b = _register_and_key(client, "user_b@example.com", "PassB99!")

    # Crawl always returns 202 immediately with the queued job id.
    r = client.post(
        "/v1/crawl",
        json={"url": fixture_server + "/", "limit": 1, "maxDepth": 0},
        headers={"X-API-Key": key_a},
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]

    # User B tries to read user A's job status — must be 404, not 200.
    r = client.get(f"/v1/crawl/{job_id}", headers={"X-API-Key": key_b})
    assert r.status_code == 404, (
        f"User B should not see user A's job, got {r.status_code}: {r.text}"
    )


# ---------------------------------------------------------------------------
# Idempotency key replay
# ---------------------------------------------------------------------------

def test_idempotency_replay_returns_same_job(client, fixture_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two POST /v1/crawl requests with the same Idempotency-Key must return the same job_id."""
    monkeypatch.setenv("API_ALLOW_PRIVATE_URLS", "1")
    _, api_key = _register_and_key(client, "idemp@example.com", "IdempPass1!")
    hdrs = {"X-API-Key": api_key, "Idempotency-Key": "test-idem-key-1"}

    r1 = client.post(
        "/v1/crawl",
        json={"url": fixture_server + "/", "limit": 1, "maxDepth": 0},
        headers=hdrs,
    )
    assert r1.status_code == 202, r1.text
    job_id_1 = r1.json()["id"]

    r2 = client.post(
        "/v1/crawl",
        json={"url": fixture_server + "/", "limit": 1, "maxDepth": 0},
        headers=hdrs,
    )
    assert r2.status_code == 202, r2.text
    job_id_2 = r2.json()["id"]

    assert job_id_1 == job_id_2, (
        f"Idempotency replay should return same job_id, got {job_id_1!r} vs {job_id_2!r}"
    )


# ---------------------------------------------------------------------------
# Rate-limit headers
# ---------------------------------------------------------------------------

def test_rate_limit_headers_present(client) -> None:
    """Authenticated requests include X-RateLimit-* response headers."""
    _, api_key = _register_and_key(client, "ratelim@example.com", "RatePass99!")

    # GET /v1/jobs always succeeds (empty list for a new user) — safe, no network needed.
    r = client.get("/v1/jobs", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    hdrs = {k.lower(): v for k, v in r.headers.items()}
    assert "x-ratelimit-limit" in hdrs, (
        f"Missing X-RateLimit-Limit header on response: {dict(r.headers)}"
    )
    assert "x-ratelimit-remaining" in hdrs
    assert "x-ratelimit-reset" in hdrs


def test_rate_limit_429_when_exceeded(monkeypatch: pytest.MonkeyPatch, client) -> None:
    """Exhaust the rate-limit bucket and verify the next call returns 429."""
    import api_auth

    # Force a tiny limit (1 request per minute) on the rate limiter.
    monkeypatch.setattr(api_auth, "_DEFAULT_PER_MIN", 1)

    _, api_key = _register_and_key(client, "ratelim2@example.com", "RatePass2!")
    hdrs = {"X-API-Key": api_key}

    # First request consumes the only slot.
    client.get("/v1/jobs", headers=hdrs)

    # Second request must be rejected.
    r = client.get("/v1/jobs", headers=hdrs)
    assert r.status_code == 429, f"Expected 429, got {r.status_code}: {r.text}"
    assert "retry-after" in {k.lower() for k in r.headers}


# ---------------------------------------------------------------------------
# SSRF guard via API
# ---------------------------------------------------------------------------

def test_scrape_blocks_private_ip(client) -> None:
    """Even with a valid API key the SSRF guard must reject private IPs."""
    _, api_key = _register_and_key(client, "ssrf@example.com", "SsrfPass1!")
    r = client.post(
        "/v1/scrape",
        json={"url": "http://192.168.1.1/"},
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_url"
