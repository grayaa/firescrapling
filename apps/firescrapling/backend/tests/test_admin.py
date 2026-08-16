"""Admin API tests — ADMIN_SECRET gate + platform-wide queries."""
from __future__ import annotations

import pytest


@pytest.fixture()
def admin_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    secret = "test-admin-secret-xyz"
    monkeypatch.setenv("ADMIN_SECRET", secret)
    return secret


def test_admin_disabled_without_secret(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    r = client.get("/v1/admin/health")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "admin_disabled"


def test_admin_rejects_bad_token(client, admin_secret: str) -> None:
    r = client.get("/v1/admin/health", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_admin_health_ok(client, admin_secret: str) -> None:
    r = client.get("/v1/admin/health", headers={"Authorization": f"Bearer {admin_secret}"})
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok"
    assert "users" in body
    assert "active_sessions" in body


def test_admin_stats_and_users(client, admin_secret: str) -> None:
    client.post("/v1/auth/register", json={"email": "adminuser@example.com", "password": "AdminPass1!"})
    hdrs = {"Authorization": f"Bearer {admin_secret}"}

    r = client.get("/v1/admin/stats", headers=hdrs)
    assert r.status_code == 200
    stats = r.json()
    assert stats["total_users"] >= 1

    r = client.get("/v1/admin/users", headers=hdrs)
    assert r.status_code == 200
    users = r.json()["users"]
    assert any(u["email"] == "adminuser@example.com" for u in users)


def test_admin_delete_user(client, admin_secret: str) -> None:
    client.post("/v1/auth/register", json={"email": "todelete@example.com", "password": "DeleteMe1!"})
    hdrs = {"Authorization": f"Bearer {admin_secret}"}
    users = client.get("/v1/admin/users?search=todelete", headers=hdrs).json()["users"]
    assert len(users) == 1
    user_id = users[0]["id"]

    r = client.delete(f"/v1/admin/users/{user_id}", headers=hdrs)
    assert r.status_code == 200

    users = client.get("/v1/admin/users?search=todelete", headers=hdrs).json()["users"]
    assert users == []


def test_admin_list_jobs(client, admin_secret: str, monkeypatch: pytest.MonkeyPatch, fixture_server: str) -> None:
    monkeypatch.setenv("API_ALLOW_PRIVATE_URLS", "1")
    client.post("/v1/auth/register", json={"email": "jobadmin@example.com", "password": "JobAdmin1!"})
    lr = client.post("/v1/auth/login", json={"email": "jobadmin@example.com", "password": "JobAdmin1!"})
    token = lr.json()["session_token"]
    kr = client.post("/v1/keys", json={"name": "k"}, headers={"Authorization": f"Bearer {token}"})
    api_key = kr.json()["key"]["value"]

    client.post(
        "/v1/crawl",
        json={"url": fixture_server + "/", "limit": 1, "maxDepth": 0},
        headers={"X-API-Key": api_key},
    )

    r = client.get("/v1/admin/jobs", headers={"Authorization": f"Bearer {admin_secret}"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1
