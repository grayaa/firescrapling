"""Users, sessions, and password hashing."""
from __future__ import annotations

import secrets
import sqlite3
import uuid
from typing import Dict, Optional

import bcrypt

from db import _get_db

# bcrypt is used directly: passlib 1.7.4 cannot drive bcrypt >= 4.1
# (it probes the removed bcrypt.__about__ and then fails every hash call).
# Hashes stay standard $2b$, so credentials created under passlib still verify.
_BCRYPT_MAX_BYTES = 72  # bcrypt ignores anything past this


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:_BCRYPT_MAX_BYTES], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def count_users() -> int:
    conn = _get_db()
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        return int(row["c"] if row else 0)
    finally:
        conn.close()


def registration_is_open() -> bool:
    """First account always allowed; after that require ALLOW_REGISTRATION=true."""
    from settings import get_settings

    if get_settings().allow_registration:
        return True
    return count_users() == 0


def register_user(email: str, password: str, full_name: str = None) -> Dict:
    conn = _get_db()
    try:
        user_id = str(uuid.uuid4())
        hashed_pw = hash_password(password)
        conn.execute(
            "INSERT INTO users (id, email, hashed_password, full_name) VALUES (?, ?, ?, ?)",
            (user_id, email.lower(), hashed_pw, full_name),
        )
        conn.commit()
        return {"success": True, "user": {"id": user_id, "email": email, "full_name": full_name}}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Email already registered"}
    finally:
        conn.close()


def login_user(email: str, password: str) -> Dict:
    conn = _get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    conn.close()

    if user and verify_password(password, user["hashed_password"]):
        return {
            "success": True,
            "user": {"id": user["id"], "email": user["email"], "full_name": user["full_name"]},
        }
    return {"success": False, "error": "Invalid email or password"}


def create_session_token(user_id: str, ttl_hours: int = 72) -> str:
    conn = _get_db()
    try:
        token = secrets.token_urlsafe(48)
        sid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO sessions (id, user_id, token, expires_at) VALUES (?, ?, ?, datetime('now', ?))",
            (sid, user_id, token, f"+{int(ttl_hours)} hours"),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def resolve_session_token(token: str) -> Optional[str]:
    if not token or not token.strip():
        return None
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (token.strip(),),
        ).fetchone()
        return row["user_id"] if row else None
    finally:
        conn.close()


def revoke_session_token(token: str) -> None:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token.strip(),))
        conn.commit()
    finally:
        conn.close()
