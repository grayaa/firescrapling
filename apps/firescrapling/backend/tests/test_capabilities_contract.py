"""Contract tests for GET /v1/capabilities — frontend branches on these fields."""
from __future__ import annotations

from settings import clear_settings_cache

# Fields the dashboard / auth / providers / settings UI read and branch on.
_CONTRACT_FIELDS: dict[str, type | tuple[type, ...]] = {
    "hosted": bool,
    "byok": bool,
    "registration_open": bool,
    "credential_source": str,
    "fetch_provider": str,
    "fetch_escalate": bool,
    "queue": bool,
    "playground": bool,
    "markdown": bool,
    "webhooks": bool,
}


def test_capabilities_contract_shape_and_self_host_defaults(client, monkeypatch) -> None:
    monkeypatch.setenv("HOSTED_MODE", "false")
    monkeypatch.delenv("PLAYGROUND_ENABLED", raising=False)
    monkeypatch.setenv("BYOK_ENABLED", "false")
    monkeypatch.setenv("FETCH_PROVIDER", "local")
    monkeypatch.setenv("QUEUE_ENABLED", "false")
    clear_settings_cache()

    r = client.get("/v1/capabilities")
    assert r.status_code == 200
    body = r.json()

    for name, expected_type in _CONTRACT_FIELDS.items():
        assert name in body, f"missing capabilities field: {name}"
        assert isinstance(body[name], expected_type), (
            f"{name}={body[name]!r} expected type {expected_type}, got {type(body[name])}"
        )

    assert body["hosted"] is False
    assert body["playground"] is False
    assert body["byok"] is False
    assert body["markdown"] is True
    assert body["webhooks"] is True
    assert body["fetch_provider"] == "local"
    assert body["credential_source"] in ("local", "platform", "byok")


def test_capabilities_byok_flag_reflects_env(client, monkeypatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("BYOK_ENABLED", "true")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    clear_settings_cache()

    body = client.get("/v1/capabilities").json()
    assert body["byok"] is True

    monkeypatch.setenv("BYOK_ENABLED", "false")
    clear_settings_cache()
    body = client.get("/v1/capabilities").json()
    assert body["byok"] is False
