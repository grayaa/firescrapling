"""Startup preflight — one INFO block so self-hosters see config failures immediately.

This function must never raise: every check is best-effort and reported in the block.
Callers (api_server lifespan) invoke it without a swallow so a true bug surfaces.
"""
from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger("firescrapling.preflight")

_GEN_KEY = (
    'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
)


def run_preflight() -> None:
    """Log a boxed config summary. Never raises."""
    lines: List[str] = ["======== FireScrapling preflight ========"]
    try:
        _append_checks(lines)
    except Exception as e:
        lines.append(f"  !! unexpected: {type(e).__name__}: {e}")
    lines.append("========================================")
    try:
        logger.info("\n".join(lines))
    except Exception:
        # Logging subsystem broken — still do not raise into lifespan.
        pass


def _append_checks(lines: List[str]) -> None:
    from settings import get_settings

    settings = get_settings()
    lines.append(f"  hosted_mode:     {settings.hosted_mode}")
    lines.append(f"  allow_registration: {settings.allow_registration}")
    lines.append(f"  byok_enabled:    {settings.byok_enabled}")
    lines.append(f"  managed_fetch:   {settings.managed_fetch_enabled}")
    lines.append(f"  fetch_provider:  {settings.resolved_provider()}")
    lines.append(f"  fetch_escalate:  {settings.fetch_escalate}")
    lines.append(f"  scrapedo:        {settings.scrapedo_configured}")
    lines.append(f"  scrapfly:        {settings.scrapfly_configured}")
    lines.append(
        f"  admin_secret:    {'configured' if settings.admin_configured else 'MISSING'}"
    )

    try:
        from api_auth import playground_enabled

        lines.append(f"  playground:      {playground_enabled()}")
    except Exception as e:
        lines.append(f"  playground:      FAIL ({type(e).__name__})")

    has_key = bool(settings.credential_encryption_keys)
    lines.append(f"  encryption_key:  {'present' if has_key else 'MISSING'}")
    if settings.byok_enabled and not has_key:
        lines.append("  !! BYOK_ENABLED but CREDENTIAL_ENCRYPTION_KEY unset")
        lines.append(f"  !! Generate: {_GEN_KEY}")
    elif not has_key:
        lines.append(f"  (optional for BYOK later) Generate: {_GEN_KEY}")

    try:
        from db import _get_db

        conn = _get_db()
        conn.execute("SELECT 1")
        conn.close()
        lines.append("  database:        ok")
    except Exception as e:
        lines.append(f"  database:        FAIL ({type(e).__name__})")

    if settings.queue_enabled:
        try:
            import redis

            r = redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
            r.ping()
            lines.append(f"  redis:           ok ({settings.redis_url})")
        except Exception as e:
            lines.append(
                f"  redis:           unreachable ({type(e).__name__}) — jobs fall back to threads"
            )
    else:
        lines.append("  redis:           skipped (QUEUE_ENABLED=false)")
