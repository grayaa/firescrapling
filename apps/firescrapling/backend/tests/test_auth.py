"""Unit tests for password hashing and account auth helpers in main.py."""
from __future__ import annotations

import pytest

import main as core


# ---------------------------------------------------------------------------
# Password hashing (bcrypt direct — passlib regression guard)
# ---------------------------------------------------------------------------

def test_hash_password_returns_string() -> None:
    h = core.hash_password("secret123")
    assert isinstance(h, str)
    assert h.startswith("$2")  # bcrypt $2b$ or $2a$ prefix


def test_verify_correct_password() -> None:
    pw = "CorrectHorseBatteryStaple"
    h = core.hash_password(pw)
    assert core.verify_password(pw, h) is True


def test_verify_wrong_password() -> None:
    h = core.hash_password("rightpassword")
    assert core.verify_password("wrongpassword", h) is False


def test_verify_empty_password() -> None:
    h = core.hash_password("realpassword")
    assert core.verify_password("", h) is False


def test_hash_is_unique_per_call() -> None:
    pw = "samepassword"
    assert core.hash_password(pw) != core.hash_password(pw)


def test_passlib_regression_register_login_roundtrip(isolated_db: str) -> None:
    """Regression: bcrypt ≥ 4.1 with passlib would raise on every hash call.
    The fix calls bcrypt directly; this test ensures registration + login succeed."""
    result = core.register_user("bcrypt@test.com", "GoodPass99!", "Bcrypt Tester")
    assert result["success"] is True

    login = core.login_user("bcrypt@test.com", "GoodPass99!")
    assert login["success"] is True
    assert login["user"]["email"] == "bcrypt@test.com"


# ---------------------------------------------------------------------------
# register_user
# ---------------------------------------------------------------------------

def test_register_creates_user(isolated_db: str) -> None:
    result = core.register_user("user@example.com", "Password1!")
    assert result["success"] is True
    assert result["user"]["email"] == "user@example.com"


def test_register_duplicate_email_fails(isolated_db: str) -> None:
    core.register_user("dup@example.com", "Pass1234!")
    result = core.register_user("dup@example.com", "OtherPass1!")
    assert result["success"] is False
    assert "already" in result["error"].lower()


def test_register_email_is_lowercased(isolated_db: str) -> None:
    result = core.register_user("MixedCase@Example.COM", "Pass1234!")
    assert result["success"] is True
    login = core.login_user("mixedcase@example.com", "Pass1234!")
    assert login["success"] is True


# ---------------------------------------------------------------------------
# login_user
# ---------------------------------------------------------------------------

def test_login_correct_credentials(isolated_db: str) -> None:
    core.register_user("login@example.com", "MyPass99!")
    result = core.login_user("login@example.com", "MyPass99!")
    assert result["success"] is True


def test_login_wrong_password(isolated_db: str) -> None:
    core.register_user("wrongpw@example.com", "RightPass1!")
    result = core.login_user("wrongpw@example.com", "WrongPass1!")
    assert result["success"] is False


def test_login_unknown_email(isolated_db: str) -> None:
    result = core.login_user("nobody@example.com", "Whatever1!")
    assert result["success"] is False


# ---------------------------------------------------------------------------
# API key lifecycle
# ---------------------------------------------------------------------------

def test_create_and_list_api_keys(isolated_db: str) -> None:
    reg = core.register_user("keys@example.com", "KeyPass1!")
    user_id = reg["user"]["id"]
    created = core.create_api_key(user_id, "my-key")
    assert created["success"] is True
    key_value = created["key"]["value"]
    assert key_value.startswith("fs_")
    # Plaintext returned once; list never stores/returns the raw key.
    keys = core.get_api_keys(user_id)
    assert len(keys) == 1
    assert keys[0]["key_value"] != key_value
    assert key_value.endswith(keys[0]["key_hint"][-4:])
    assert core.resolve_api_key(key_value) is not None


def test_delete_api_key(isolated_db: str) -> None:
    reg = core.register_user("delkeys@example.com", "DelPass1!")
    user_id = reg["user"]["id"]
    created = core.create_api_key(user_id, "to-delete")
    key_id = created["key"]["id"]

    result = core.delete_api_key(user_id, key_id)
    assert result["success"] is True
    assert core.get_api_keys(user_id) == []


def test_resolve_api_key(isolated_db: str) -> None:
    reg = core.register_user("resolve@example.com", "ResPass1!")
    user_id = reg["user"]["id"]
    created = core.create_api_key(user_id, "resolve-key")
    raw_key = created["key"]["value"]

    resolved = core.resolve_api_key(raw_key)
    assert resolved is not None
    assert resolved["user_id"] == user_id


def test_resolve_nonexistent_key(isolated_db: str) -> None:
    assert core.resolve_api_key("fs_doesnotexist") is None


# ---------------------------------------------------------------------------
# Session tokens
# ---------------------------------------------------------------------------

def test_session_token_roundtrip(isolated_db: str) -> None:
    reg = core.register_user("session@example.com", "SessPass1!")
    user_id = reg["user"]["id"]
    token = core.create_session_token(user_id)
    assert core.resolve_session_token(token) == user_id


def test_revoked_session_token(isolated_db: str) -> None:
    reg = core.register_user("revoke@example.com", "RevokePass1!")
    user_id = reg["user"]["id"]
    token = core.create_session_token(user_id)
    core.revoke_session_token(token)
    assert core.resolve_session_token(token) is None
