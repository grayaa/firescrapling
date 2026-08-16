"""Tests for BYOK provider credential crypto + FetchContext resolution."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet


@pytest.fixture()
def byok_env(isolated_db, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("BYOK_ENABLED", "true")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", key)
    monkeypatch.setenv("MANAGED_FETCH_ENABLED", "true")
    from settings import clear_settings_cache

    clear_settings_cache()
    yield key
    clear_settings_cache()


def test_encrypt_roundtrip(byok_env):
    from provider_credentials import decrypt_api_key, encrypt_api_key, key_hint

    blob = encrypt_api_key("secret-token-abcdef")
    assert decrypt_api_key(blob) == "secret-token-abcdef"
    assert key_hint("secret-token-abcdef") == "cdef"
    assert "secret" not in key_hint("secret-token-abcdef")


def test_wrong_key_fails(byok_env, monkeypatch):
    from provider_credentials import CredentialUndecryptable, decrypt_api_key, encrypt_api_key
    from settings import clear_settings_cache

    blob = encrypt_api_key("my-api-key-value")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    clear_settings_cache()
    with pytest.raises(CredentialUndecryptable):
        decrypt_api_key(blob)


def test_key_rotation_multifernet(byok_env, monkeypatch):
    """Credential written under key A still decrypts after B becomes primary."""
    from provider_credentials import decrypt_api_key, encrypt_api_key
    from settings import clear_settings_cache

    key_a = byok_env
    key_b = Fernet.generate_key().decode()
    blob = encrypt_api_key("rotate-me-secret-xx")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEYS", f"{key_b},{key_a}")
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)
    clear_settings_cache()
    assert decrypt_api_key(blob) == "rotate-me-secret-xx"
    # Re-encrypt onto primary B
    new_blob = encrypt_api_key("rotate-me-secret-xx")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEYS", key_b)
    clear_settings_cache()
    assert decrypt_api_key(new_blob) == "rotate-me-secret-xx"


@pytest.mark.parametrize(
    "preferred,scrapedo,scrapfly,expect",
    [
        (None, True, False, "scrapedo"),
        (None, False, True, "scrapfly"),
        (None, True, True, "scrapedo"),
        (None, False, False, "local"),
        ("scrapedo", True, True, "scrapedo"),
        ("scrapfly", True, True, "scrapfly"),
        ("scrapedo", False, True, "scrapfly"),
        ("scrapfly", True, False, "scrapedo"),
        ("auto", True, True, "scrapedo"),
        ("auto", False, True, "scrapfly"),
        ("scrapedo", False, False, "local"),
        ("scrapfly", False, False, "local"),
    ],
)
def test_platform_resolution_table(byok_env, monkeypatch, preferred, scrapedo, scrapfly, expect):
    from provider_credentials import build_fetch_context
    from settings import clear_settings_cache

    if scrapedo:
        monkeypatch.setenv("SCRAPE_API_KEY", "platform-sd-key")
    else:
        monkeypatch.delenv("SCRAPE_API_KEY", raising=False)
        monkeypatch.delenv("SCRAPE_DO_API_KEY", raising=False)
    if scrapfly:
        monkeypatch.setenv("SCRAPFLY_API_KEY", "platform-sf-key")
    else:
        monkeypatch.delenv("SCRAPFLY_API_KEY", raising=False)
    monkeypatch.setenv("MANAGED_FETCH_ENABLED", "true")
    clear_settings_cache()
    ctx = build_fetch_context(None, preferred_provider=preferred)
    assert ctx.provider == expect
    if expect == "local":
        assert ctx.source == "local"
    else:
        assert ctx.source == "platform"


def test_create_list_no_plaintext(byok_env, authed):
    client, _api_key, session = authed
    r = client.post(
        "/v1/providers",
        json={"provider": "scrapedo", "api_key": "test-key-abcdefgh", "label": "dev"},
        headers={"Authorization": f"Bearer {session}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    prov = body["provider"]
    assert "encrypted_key" not in prov
    assert "api_key" not in prov
    assert "test-key" not in r.text
    assert prov["key_hint"] == "efgh"
    assert prov["provider"] == "scrapedo"

    r = client.get("/v1/providers", headers={"Authorization": f"Bearer {session}"})
    assert r.status_code == 200
    assert len(r.json()["providers"]) == 1
    assert "test-key" not in r.text


def test_build_fetch_context_byok(byok_env, isolated_db):
    import main as core
    from provider_credentials import build_fetch_context, create_provider_credential

    uid = str(__import__("uuid").uuid4())
    conn = core._get_db()
    conn.execute(
        "INSERT INTO users (id, email, hashed_password) VALUES (?, ?, ?)",
        (uid, "byok@example.com", core.hash_password("Pass1234!")),
    )
    conn.commit()
    conn.close()

    create_provider_credential(uid, "scrapedo", "user-byok-key-1111", label="u1")
    ctx = build_fetch_context(uid)
    assert ctx.source == "byok"
    assert ctx.provider == "scrapedo"
    assert ctx.api_key == "user-byok-key-1111"
    assert ctx.credential_id


def test_build_fetch_context_platform(byok_env, monkeypatch):
    from provider_credentials import build_fetch_context
    from settings import clear_settings_cache

    monkeypatch.setenv("SCRAPE_API_KEY", "platform-scrape-do-key")
    monkeypatch.setenv("MANAGED_FETCH_ENABLED", "true")
    clear_settings_cache()
    ctx = build_fetch_context(None)
    assert ctx.source == "platform"
    assert ctx.provider == "scrapedo"
    assert ctx.api_key == "platform-scrape-do-key"


def test_managed_off_local_only(byok_env, monkeypatch):
    from provider_credentials import build_fetch_context
    from settings import clear_settings_cache

    monkeypatch.setenv("SCRAPE_API_KEY", "platform-key-xxxx")
    monkeypatch.setenv("MANAGED_FETCH_ENABLED", "false")
    clear_settings_cache()
    ctx = build_fetch_context(None)
    assert ctx.source == "local"
    assert ctx.provider == "local"
    assert ctx.api_key is None


def test_two_users_isolated_keys(byok_env, isolated_db, monkeypatch):
    """Two accounts with different Scrape.do keys resolve distinct FetchContexts."""
    import uuid

    import main as core
    from fetch_provider import ScrapedoFetcher
    from provider_credentials import build_fetch_context, create_provider_credential
    from settings import clear_settings_cache

    monkeypatch.setenv("MANAGED_FETCH_ENABLED", "false")
    clear_settings_cache()

    keys_seen = []

    def fake_fetch(self, url, **kwargs):
        keys_seen.append(self._api_key)
        from fetch_provider import FetchResult

        return FetchResult(html_content="<html><body>ok enough text here for classify</body></html>", url=url, status=200)

    monkeypatch.setattr(ScrapedoFetcher, "fetch", fake_fetch)

    users = []
    for i, key in enumerate(("aaaa1111bbbb2222", "cccc3333dddd4444")):
        uid = str(uuid.uuid4())
        conn = core._get_db()
        conn.execute(
            "INSERT INTO users (id, email, hashed_password) VALUES (?, ?, ?)",
            (uid, f"u{i}@example.com", core.hash_password("Pass1234!")),
        )
        conn.commit()
        conn.close()
        create_provider_credential(uid, "scrapedo", key)
        users.append(uid)

    from scraping_engine import fetch_with_retries

    for uid in users:
        ctx = build_fetch_context(uid)
        fetch_with_retries("https://example.com/", timeout=5, ctx=ctx)

    assert keys_seen == ["aaaa1111bbbb2222", "cccc3333dddd4444"]


def test_byok_disabled_rejects_create(isolated_db, authed, monkeypatch):
    monkeypatch.setenv("BYOK_ENABLED", "false")
    from settings import clear_settings_cache

    clear_settings_cache()
    client, _k, session = authed
    r = client.post(
        "/v1/providers",
        json={"provider": "scrapedo", "api_key": "test-key-abcdefgh"},
        headers={"Authorization": f"Bearer {session}"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "byok_disabled"
