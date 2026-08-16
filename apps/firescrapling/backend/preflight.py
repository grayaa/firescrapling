"""Startup preflight — one INFO block so self-hosters see config failures immediately."""
from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger("firescrapling.preflight")

_GEN_KEY = (
    'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
)


def run_preflight() -> None:
    from settings import get_settings

    settings = get_settings()
    lines: List[str] = []
    lines.append("======== FireScrapling preflight ========")
    lines.append(f"  hosted_mode:     {settings.hosted_mode}")
    lines.append(f"  allow_registration: {settings.allow_registration}")
    lines.append(f"  byok_enabled:    {settings.byok_enabled}")
    lines.append(f"  managed_fetch:   {settings.managed_fetch_enabled}")
    lines.append(f"  fetch_provider:  {settings.resolved_provider()}")
    lines.append(f"  fetch_escalate:  {settings.fetch_escalate}")
    lines.append(f"  scrapedo:        {settings.scrapedo_configured}")
    lines.append(f"  scrapfly:        {settings.scrapfly_configured}")

    # Playground
    from api_auth import playground_enabled

    lines.append(f"  playground:      {playground_enabled()}")

    # Encryption
    has_key = bool(settings.credential_encryption_keys)
    lines.append(f"  encryption_key:  {'present' if has_key else 'MISSING'}")
    if settings.byok_enabled and not has_key:
        lines.append("  !! BYOK_ENABLED but CREDENTIAL_ENCRYPTION_KEY unset")
        lines.append(f"  !! Generate: {_GEN_KEY}")
    elif not has_key:
        lines.append(f"  (optional for BYOK later) Generate: {_GEN_KEY}")

    # DB
    try:
        from db import _get_db

        conn = _get_db()
        conn.execute("SELECT 1")
        conn.close()
        lines.append("  database:        ok")
    except Exception as e:
        lines.append(f"  database:        FAIL ({type(e).__name__})")

    # Redis
    if settings.queue_enabled:
        try:
            import redis

            r = redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
            r.ping()
            lines.append(f"  redis:           ok ({settings.redis_url})")
        except Exception as e:
            lines.append(f"  redis:           unreachable ({type(e).__name__}) — jobs fall back to threads")
    else:
        lines.append("  redis:           skipped (QUEUE_ENABLED=false)")

    lines.append("========================================")
    logger.info("\n".join(lines))
