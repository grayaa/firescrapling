"""BYOK provider credentials — encrypted at rest, never logged in plaintext."""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from fetch_context import FetchContext
from settings import get_settings

logger = logging.getLogger(__name__)

ProviderKind = Literal["scrapedo", "scrapfly"]


class CredentialUndecryptable(Exception):
    """Stored credential cannot be decrypted with configured keys."""

    code = "credential_undecryptable"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _db():
    from db import _get_db

    return _get_db()


def _multi_fernet() -> MultiFernet:
    settings = get_settings()
    raw_keys = settings.credential_encryption_keys
    if not raw_keys:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY is required when BYOK is enabled "
            "(generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
        )
    fernets: List[Fernet] = []
    for raw in raw_keys:
        try:
            fernets.append(Fernet(raw.encode("ascii") if isinstance(raw, str) else raw))
        except Exception as e:
            raise RuntimeError(
                "CREDENTIAL_ENCRYPTION_KEY(S) invalid (expect Fernet url-safe base64 key)"
            ) from e
    return MultiFernet(fernets)


def encrypt_api_key(plaintext: str) -> bytes:
    """Encrypt with the primary (newest) key."""
    return _multi_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_api_key(blob: bytes) -> str:
    """Decrypt trying all configured keys (rotation-safe)."""
    try:
        return _multi_fernet().decrypt(blob).decode("utf-8")
    except InvalidToken as e:
        raise CredentialUndecryptable(
            "Failed to decrypt provider credential (wrong CREDENTIAL_ENCRYPTION_KEY?)"
        ) from e


def key_hint(plaintext: str) -> str:
    s = (plaintext or "").strip()
    if len(s) <= 4:
        return "****"
    return s[-4:]


def create_provider_credential(
    user_id: str,
    provider: ProviderKind,
    api_key: str,
    *,
    label: Optional[str] = None,
    country: Optional[str] = None,
    proxy_pool: Optional[str] = None,
    residential_pool: Optional[str] = None,
) -> Dict[str, Any]:
    if provider not in ("scrapedo", "scrapfly"):
        raise ValueError("provider must be scrapedo or scrapfly")
    key = (api_key or "").strip()
    if len(key) < 8:
        raise ValueError("api_key too short")

    conn = _db()
    try:
        blob = encrypt_api_key(key)
        now = _utcnow()
        hint = key_hint(key)
        existing = conn.execute(
            "SELECT id FROM provider_credentials WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        ).fetchone()
        if existing:
            cid = existing["id"]
            conn.execute(
                """
                UPDATE provider_credentials SET
                  label = ?, encrypted_key = ?, key_hint = ?, proxy_pool = ?,
                  residential_pool = ?, country = ?, status = 'unverified',
                  created_at = ?, last_used_at = NULL
                WHERE id = ?
                """,
                (label, blob, hint, proxy_pool, residential_pool, country, now, cid),
            )
        else:
            cid = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO provider_credentials
                  (id, user_id, provider, label, encrypted_key, key_hint, proxy_pool,
                   residential_pool, country, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unverified', ?)
                """,
                (
                    cid,
                    user_id,
                    provider,
                    label,
                    blob,
                    hint,
                    proxy_pool,
                    residential_pool,
                    country,
                    now,
                ),
            )
        row = conn.execute(
            "SELECT id, provider, label, key_hint, proxy_pool, residential_pool, country, status, created_at, last_used_at "
            "FROM provider_credentials WHERE id = ?",
            (cid,),
        ).fetchone()
        conn.commit()
        return _row_public(row)
    finally:
        conn.close()


def list_provider_credentials(user_id: str) -> List[Dict[str, Any]]:
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT id, provider, label, key_hint, proxy_pool, residential_pool, country, status, created_at, last_used_at "
            "FROM provider_credentials WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [_row_public(r) for r in rows]
    finally:
        conn.close()


def get_credential_row(user_id: str, credential_id: str) -> Optional[sqlite3.Row]:
    conn = _db()
    try:
        return conn.execute(
            "SELECT * FROM provider_credentials WHERE id = ? AND user_id = ?",
            (credential_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def delete_provider_credential(user_id: str, credential_id: str) -> bool:
    conn = _db()
    try:
        cur = conn.execute(
            "DELETE FROM provider_credentials WHERE id = ? AND user_id = ?",
            (credential_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def set_credential_status(user_id: str, credential_id: str, status: str) -> None:
    conn = _db()
    try:
        conn.execute(
            "UPDATE provider_credentials SET status = ? WHERE id = ? AND user_id = ?",
            (status, credential_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def touch_credential_used(credential_id: str) -> None:
    conn = _db()
    try:
        conn.execute(
            "UPDATE provider_credentials SET last_used_at = ? WHERE id = ?",
            (_utcnow(), credential_id),
        )
        conn.commit()
    finally:
        conn.close()


def reencrypt_all_credentials() -> int:
    """Re-encrypt every row onto the primary key. Returns count updated."""
    conn = _db()
    try:
        rows = conn.execute("SELECT id, encrypted_key FROM provider_credentials").fetchall()
        n = 0
        for row in rows:
            blob = row["encrypted_key"]
            if isinstance(blob, memoryview):
                blob = blob.tobytes()
            plaintext = decrypt_api_key(bytes(blob))
            new_blob = encrypt_api_key(plaintext)
            conn.execute(
                "UPDATE provider_credentials SET encrypted_key = ? WHERE id = ?",
                (new_blob, row["id"]),
            )
            n += 1
        conn.commit()
        return n
    finally:
        conn.close()


def _decrypt_row(row: sqlite3.Row) -> str:
    blob = row["encrypted_key"]
    if isinstance(blob, memoryview):
        blob = blob.tobytes()
    return decrypt_api_key(bytes(blob))


def _platform_fetch_context(
    preferred_provider: Optional[str],
) -> Optional[FetchContext]:
    """First configured platform provider from an ordered candidate list."""
    settings = get_settings()
    preferred = (preferred_provider or "auto").strip().lower()
    if preferred in ("scrapedo", "scrapfly"):
        order = [preferred]
        for p in ("scrapedo", "scrapfly"):
            if p not in order:
                order.append(p)
    else:
        # auto / unset: prefer Scrape.do
        order = ["scrapedo", "scrapfly"]

    for name in order:
        if name == "scrapedo" and settings.scrapedo_configured:
            return FetchContext(
                provider="scrapedo",
                api_key=settings.scrapedo_api_key,
                proxy_pool=None,
                residential_pool=settings.scrapfly_residential_pool,
                country=settings.scrapfly_country,
                source="platform",
                credential_id=None,
            )
        if name == "scrapfly" and settings.scrapfly_configured:
            return FetchContext(
                provider="scrapfly",
                api_key=settings.scrapfly_api_key,
                proxy_pool=settings.scrapfly_proxy_pool,
                residential_pool=settings.scrapfly_residential_pool,
                country=settings.scrapfly_country,
                source="platform",
                credential_id=None,
            )
    return None


def build_fetch_context(
    user_id: Optional[str] = None,
    *,
    credential_id: Optional[str] = None,
    preferred_provider: Optional[str] = None,
) -> FetchContext:
    """Resolve BYOK → platform managed → local."""
    settings = get_settings()

    # Prefer explicit credential, else active BYOK for user
    if user_id and settings.byok_enabled:
        conn = _db()
        try:
            row = None
            if credential_id:
                row = conn.execute(
                    "SELECT * FROM provider_credentials WHERE id = ? AND user_id = ?",
                    (credential_id, user_id),
                ).fetchone()
            if row is None:
                order: List[str] = []
                if preferred_provider in ("scrapedo", "scrapfly"):
                    order.append(preferred_provider)
                for p in ("scrapedo", "scrapfly"):
                    if p not in order:
                        order.append(p)
                for p in order:
                    row = conn.execute(
                        "SELECT * FROM provider_credentials WHERE user_id = ? AND provider = ? "
                        "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END LIMIT 1",
                        (user_id, p),
                    ).fetchone()
                    if row:
                        break
            if row is not None:
                try:
                    key = _decrypt_row(row)
                except CredentialUndecryptable:
                    logger.warning(
                        "credential undecryptable id=%s — marking rejected",
                        row["id"],
                    )
                    conn.execute(
                        "UPDATE provider_credentials SET status = 'rejected' WHERE id = ?",
                        (row["id"],),
                    )
                    conn.commit()
                    raise
                return FetchContext(
                    provider=row["provider"],  # type: ignore[arg-type]
                    api_key=key,
                    proxy_pool=row["proxy_pool"] or settings.scrapfly_proxy_pool,
                    residential_pool=row["residential_pool"] or settings.scrapfly_residential_pool,
                    country=row["country"] or settings.scrapfly_country,
                    source="byok",
                    credential_id=row["id"],
                )
        finally:
            conn.close()

    # Platform managed env keys (plan-gated when a subscription row exists)
    from billing import can_use_managed_fetch

    if can_use_managed_fetch(user_id):
        platform = _platform_fetch_context(preferred_provider)
        if platform is not None:
            return platform

    return FetchContext(
        provider="local",
        api_key=None,
        proxy_pool=None,
        residential_pool=None,
        country=None,
        source="local",
        credential_id=None,
    )


def _row_public(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "provider": row["provider"],
        "label": row["label"],
        "key_hint": row["key_hint"],
        "proxy_pool": row["proxy_pool"],
        "residential_pool": row["residential_pool"],
        "country": row["country"],
        "status": row["status"],
        "created_at": row["created_at"],
        "last_used_at": row["last_used_at"],
    }


def verify_credential_live(user_id: str, credential_id: str) -> Dict[str, Any]:
    """Cheap live check against example.com; updates status."""
    row = get_credential_row(user_id, credential_id)
    if row is None:
        raise LookupError("credential not found")
    try:
        key = _decrypt_row(row)
    except CredentialUndecryptable:
        set_credential_status(user_id, credential_id, "rejected")
        raise
    from fetch_provider import ScrapedoFetcher, ScrapflyFetcher

    try:
        if row["provider"] == "scrapedo":
            result = ScrapedoFetcher(key).fetch("https://example.com/", render_js=False, asp=False)
        else:
            result = ScrapflyFetcher(key).fetch(
                "https://example.com/",
                render_js=False,
                asp=False,
                proxy_pool="public_datacenter_pool",
            )
        ok = result.status < 400 and len(result.html_content or "") > 20
    except Exception as e:
        logger.info("credential verify failed id=%s err=%s", credential_id, type(e).__name__)
        set_credential_status(user_id, credential_id, "rejected")
        return {"success": False, "status": "rejected", "message": "Verification fetch failed"}

    status = "active" if ok else "rejected"
    set_credential_status(user_id, credential_id, status)
    if ok:
        touch_credential_used(credential_id)
    return {"success": ok, "status": status, "http_status": result.status}
