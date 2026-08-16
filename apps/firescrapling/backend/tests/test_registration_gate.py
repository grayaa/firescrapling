"""ALLOW_REGISTRATION gate — first user always; then closed unless flag on."""
from __future__ import annotations


def test_first_registration_succeeds_when_closed(client, monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_REGISTRATION", "false")
    from settings import clear_settings_cache

    clear_settings_cache()
    r = client.post(
        "/v1/auth/register",
        json={"email": "ops@example.com", "password": "OpsPass99!"},
    )
    assert r.status_code == 200
    caps = client.get("/v1/capabilities").json()
    assert caps["registration_open"] is False


def test_second_registration_403_by_default(client, monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_REGISTRATION", "false")
    from settings import clear_settings_cache

    clear_settings_cache()
    assert (
        client.post(
            "/v1/auth/register",
            json={"email": "one@example.com", "password": "OnePass99!"},
        ).status_code
        == 200
    )
    r = client.post(
        "/v1/auth/register",
        json={"email": "two@example.com", "password": "TwoPass99!"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "registration_closed"


def test_registration_open_when_flag_on(client, monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    from settings import clear_settings_cache

    clear_settings_cache()
    assert (
        client.post(
            "/v1/auth/register",
            json={"email": "a@example.com", "password": "AaaPass99!"},
        ).status_code
        == 200
    )
    r = client.post(
        "/v1/auth/register",
        json={"email": "b@example.com", "password": "BbbPass99!"},
    )
    assert r.status_code == 200
    assert client.get("/v1/capabilities").json()["registration_open"] is True
