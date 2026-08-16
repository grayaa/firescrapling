"""Unit tests for security_url.validate_request_url (SSRF guard)."""
from __future__ import annotations

import pytest

from security_url import validate_request_url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(url: str, **kw: bool) -> None:
    """Assert the URL is allowed (validate_request_url returns None)."""
    err = validate_request_url(url, **kw)
    assert err is None, f"Expected {url!r} to be allowed but got: {err!r}"


def _blocked(url: str, **kw: bool) -> None:
    """Assert the URL is blocked (validate_request_url returns a message)."""
    err = validate_request_url(url, **kw)
    assert err is not None, f"Expected {url!r} to be blocked but it was allowed"


# ---------------------------------------------------------------------------
# Scheme checks
# ---------------------------------------------------------------------------

def test_https_public_allowed() -> None:
    _ok("https://example.com/page")


def test_http_public_allowed() -> None:
    _ok("http://example.com/page")


def test_ftp_blocked() -> None:
    _blocked("ftp://example.com/file")


def test_file_blocked() -> None:
    _blocked("file:///etc/passwd")


def test_empty_url_blocked() -> None:
    _blocked("")


def test_non_string_blocked() -> None:
    err = validate_request_url(None)  # type: ignore[arg-type]
    assert err is not None


# ---------------------------------------------------------------------------
# localhost / loopback
# ---------------------------------------------------------------------------

def test_localhost_blocked() -> None:
    _blocked("http://localhost/")


def test_127_blocked() -> None:
    _blocked("http://127.0.0.1/")


def test_0_0_0_0_blocked() -> None:
    _blocked("http://0.0.0.0/")


# ---------------------------------------------------------------------------
# Private RFC 1918 ranges
# ---------------------------------------------------------------------------

def test_10_x_blocked() -> None:
    _blocked("http://10.1.2.3/")


def test_172_16_blocked() -> None:
    _blocked("http://172.16.0.1/")


def test_192_168_blocked() -> None:
    _blocked("http://192.168.1.1/")


# ---------------------------------------------------------------------------
# Link-local / local hostnames
# ---------------------------------------------------------------------------

def test_link_local_blocked() -> None:
    _blocked("http://169.254.169.254/latest/meta-data/")


def test_local_mdns_blocked() -> None:
    _blocked("http://mydevice.local/")


# ---------------------------------------------------------------------------
# URL too long
# ---------------------------------------------------------------------------

def test_url_too_long_blocked() -> None:
    _blocked("https://example.com/" + "a" * 8200)


# ---------------------------------------------------------------------------
# force_public_only overrides API_ALLOW_PRIVATE_URLS env
# ---------------------------------------------------------------------------

def test_force_public_only_blocks_localhost_even_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_ALLOW_PRIVATE_URLS", "1")
    _blocked("http://localhost/", force_public_only=True)


def test_allow_private_env_permits_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_ALLOW_PRIVATE_URLS", "1")
    _ok("http://localhost/")
