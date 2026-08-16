"""Unit tests for webhook_delivery.sign_body."""
from __future__ import annotations

from webhook_delivery import sign_body


def test_sign_body_has_sha256_prefix() -> None:
    sig = sign_body("mysecret", b"hello")
    assert sig.startswith("sha256=")


def test_sign_body_is_deterministic() -> None:
    sig1 = sign_body("secret", b"body")
    sig2 = sign_body("secret", b"body")
    assert sig1 == sig2


def test_sign_body_different_secret_differs() -> None:
    assert sign_body("secret-a", b"body") != sign_body("secret-b", b"body")


def test_sign_body_different_body_differs() -> None:
    assert sign_body("secret", b"body-a") != sign_body("secret", b"body-b")


def test_sign_body_hex_length() -> None:
    sig = sign_body("secret", b"anything")
    # "sha256=" + 64 hex chars
    assert len(sig) == 7 + 64


def test_sign_body_empty_payload() -> None:
    sig = sign_body("secret", b"")
    assert sig.startswith("sha256=")
    assert len(sig) == 71
