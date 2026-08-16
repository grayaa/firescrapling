"""HTTP tests for /v1/providers — BYOK gate must not leave orphan rows."""
from __future__ import annotations

from settings import clear_settings_cache


def test_post_providers_byok_disabled_returns_409_and_writes_nothing(
    client, authed, monkeypatch, isolated_db
) -> None:
    monkeypatch.setenv("BYOK_ENABLED", "false")
    clear_settings_cache()

    _client, _api_key, session = authed
    headers = {"Authorization": f"Bearer {session}"}

    # Resolve user id from session for a direct DB count.
    import main as core

    user_id = core.resolve_session_token(session)
    assert user_id

    from provider_credentials import list_provider_credentials
    from db import _get_db

    assert list_provider_credentials(user_id) == []

    r = _client.post(
        "/v1/providers",
        json={"provider": "scrapedo", "api_key": "test-key-abcdefgh"},
        headers=headers,
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "byok_disabled"

    # Storage side: no credential row for this user (or globally for this attempt).
    assert list_provider_credentials(user_id) == []
    conn = _get_db()
    try:
        n = conn.execute("SELECT COUNT(*) AS c FROM provider_credentials").fetchone()["c"]
    finally:
        conn.close()
    assert n == 0
