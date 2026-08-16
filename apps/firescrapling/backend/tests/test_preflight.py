"""Preflight startup checks — must report state and never raise."""
from __future__ import annotations

import logging

import pytest

from preflight import _GEN_KEY, run_preflight
from settings import clear_settings_cache


@pytest.fixture(autouse=True)
def _clear_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


def _preflight_text(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


def test_preflight_reports_each_check_pass_fail(isolated_db, monkeypatch, caplog) -> None:
    monkeypatch.setenv("HOSTED_MODE", "false")
    monkeypatch.setenv("PLAYGROUND_ENABLED", "false")
    monkeypatch.setenv("QUEUE_ENABLED", "false")
    monkeypatch.setenv("FETCH_PROVIDER", "local")
    monkeypatch.delenv("SCRAPE_API_KEY", raising=False)
    monkeypatch.delenv("SCRAPFLY_API_KEY", raising=False)
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEYS", raising=False)
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    clear_settings_cache()

    with caplog.at_level(logging.INFO, logger="firescrapling.preflight"):
        run_preflight()

    text = _preflight_text(caplog)
    assert "hosted_mode:     False" in text
    assert "playground:      False" in text
    assert "scrapedo:        False" in text
    assert "scrapfly:        False" in text
    assert "encryption_key:  MISSING" in text
    assert "admin_secret:    MISSING" in text
    assert "database:        ok" in text
    assert "redis:           skipped (QUEUE_ENABLED=false)" in text
    assert "======== FireScrapling preflight ========" in text


def test_preflight_reports_providers_and_admin_when_configured(
    isolated_db, monkeypatch, caplog
) -> None:
    monkeypatch.setenv("HOSTED_MODE", "true")
    monkeypatch.setenv("PLAYGROUND_ENABLED", "true")
    monkeypatch.setenv("SCRAPE_API_KEY", "test-scrape-do-key")
    monkeypatch.setenv("ADMIN_SECRET", "admin-secret-for-tests")
    monkeypatch.setenv("QUEUE_ENABLED", "false")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    clear_settings_cache()

    with caplog.at_level(logging.INFO, logger="firescrapling.preflight"):
        run_preflight()

    text = _preflight_text(caplog)
    assert "hosted_mode:     True" in text
    assert "playground:      True" in text
    assert "scrapedo:        True" in text
    assert "encryption_key:  present" in text
    assert "admin_secret:    configured" in text
    assert "database:        ok" in text


def test_preflight_emits_fernet_generation_command_when_key_missing(
    isolated_db, monkeypatch, caplog
) -> None:
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEYS", raising=False)
    monkeypatch.setenv("QUEUE_ENABLED", "false")
    clear_settings_cache()

    with caplog.at_level(logging.INFO, logger="firescrapling.preflight"):
        run_preflight()

    text = _preflight_text(caplog)
    assert "encryption_key:  MISSING" in text
    assert _GEN_KEY in text
    assert "Fernet.generate_key()" in text


def test_preflight_reports_db_fail_without_raising(monkeypatch, caplog) -> None:
    monkeypatch.setenv("QUEUE_ENABLED", "false")
    clear_settings_cache()

    import db

    def _boom():
        raise RuntimeError("db exploded")

    monkeypatch.setattr(db, "_get_db", _boom)

    with caplog.at_level(logging.INFO, logger="firescrapling.preflight"):
        run_preflight()  # must not raise

    text = _preflight_text(caplog)
    assert "database:        FAIL (RuntimeError)" in text


def test_preflight_reports_redis_unreachable_without_raising(
    isolated_db, monkeypatch, caplog
) -> None:
    monkeypatch.setenv("QUEUE_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    clear_settings_cache()

    with caplog.at_level(logging.INFO, logger="firescrapling.preflight"):
        run_preflight()  # must not raise

    text = _preflight_text(caplog)
    assert "redis:           unreachable" in text
    assert "jobs fall back to threads" in text


def test_preflight_never_raises_even_if_checks_explode(monkeypatch, caplog) -> None:
    import preflight as pf

    def _boom(_lines: list) -> None:
        raise RuntimeError("settings hard-fail")

    monkeypatch.setattr(pf, "_append_checks", _boom)

    with caplog.at_level(logging.INFO, logger="firescrapling.preflight"):
        run_preflight()  # must not raise

    text = _preflight_text(caplog)
    assert "unexpected: RuntimeError" in text
    assert "settings hard-fail" in text
