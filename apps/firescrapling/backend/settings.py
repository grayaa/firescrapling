"""Central settings for FireScrapling backend (env-driven)."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal, Optional


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    """Lazy env reads — keep simple (no pydantic-settings dep required)."""

    @property
    def scrapfly_api_key(self) -> str:
        return (os.environ.get("SCRAPFLY_API_KEY") or "").strip()

    @property
    def scrapfly_configured(self) -> bool:
        return bool(self.scrapfly_api_key)

    @property
    def scrapedo_api_key(self) -> str:
        # Prefer SCRAPE_API_KEY (user convention); accept SCRAPE_DO_API_KEY alias.
        return (
            os.environ.get("SCRAPE_API_KEY")
            or os.environ.get("SCRAPE_DO_API_KEY")
            or ""
        ).strip()

    @property
    def scrapedo_configured(self) -> bool:
        return bool(self.scrapedo_api_key)

    @property
    def paid_fetch_configured(self) -> bool:
        return self.scrapedo_configured or self.scrapfly_configured

    @property
    def scrapfly_proxy_pool(self) -> str:
        return (os.environ.get("SCRAPFLY_PROXY_POOL") or "public_datacenter_pool").strip()

    @property
    def scrapfly_residential_pool(self) -> str:
        return (os.environ.get("SCRAPFLY_RESIDENTIAL_POOL") or "public_residential_pool").strip()

    @property
    def scrapfly_country(self) -> Optional[str]:
        c = (os.environ.get("SCRAPFLY_COUNTRY") or "").strip()
        return c or None

    @property
    def scrapfly_default_render_js(self) -> bool:
        # Budget-safe defaults — escalation enables JS/ASP only when needed.
        return _bool("SCRAPFLY_DEFAULT_RENDER_JS", False)

    @property
    def scrapfly_default_asp(self) -> bool:
        return _bool("SCRAPFLY_DEFAULT_ASP", False)

    @property
    def fetch_escalate(self) -> bool:
        """Cheap-first probe ladder when client omits renderJs/asp/proxyPool."""
        return _bool("FETCH_ESCALATE", True)

    @property
    def fetch_profile_ttl_seconds(self) -> int:
        try:
            return max(60, int(os.environ.get("FETCH_PROFILE_TTL_SECONDS") or "86400"))
        except ValueError:
            return 86400

    @property
    def fetch_provider(self) -> Literal["auto", "scrapfly", "scrapedo", "local"]:
        v = (os.environ.get("FETCH_PROVIDER") or "auto").strip().lower()
        if v in ("auto", "scrapfly", "scrapedo", "local"):
            return v  # type: ignore[return-value]
        return "auto"

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL. Default sqlite file under backend data/db (local/tests)."""
        env = (os.environ.get("DATABASE_URL") or "").strip()
        if env:
            return env
        from db import default_database_url

        return default_database_url()

    @property
    def redis_url(self) -> str:
        return (os.environ.get("REDIS_URL") or "redis://localhost:6379/0").strip()

    @property
    def queue_enabled(self) -> bool:
        """When false, fall back to in-process threads (tests / no Redis)."""
        return _bool("QUEUE_ENABLED", True)

    @property
    def worker_concurrency(self) -> int:
        try:
            return max(1, int(os.environ.get("WORKER_CONCURRENCY") or "2"))
        except ValueError:
            return 2

    @property
    def byok_enabled(self) -> bool:
        return _bool("BYOK_ENABLED", False)

    @property
    def hosted_mode(self) -> bool:
        """Commercial/hosted SaaS surface (billing, plan gates). Default off for OSS self-host."""
        return _bool("HOSTED_MODE", False)

    @property
    def allow_registration(self) -> bool:
        """When false, only the first account (empty users table) may register."""
        return _bool("ALLOW_REGISTRATION", True)

    @property
    def managed_fetch_enabled(self) -> bool:
        """Platform env keys (SCRAPE_API_KEY / SCRAPFLY_API_KEY) as fallback."""
        return _bool("MANAGED_FETCH_ENABLED", True)

    @property
    def admin_configured(self) -> bool:
        return bool((os.environ.get("ADMIN_SECRET") or "").strip())

    @property
    def rate_limit_per_minute(self) -> int:
        try:
            return max(1, int(os.environ.get("RATE_LIMIT_PER_MINUTE") or "60"))
        except ValueError:
            return 60

    @property
    def database_backend(self) -> str:
        url = (os.environ.get("DATABASE_URL") or "").strip().lower()
        if url.startswith("postgres"):
            return "postgres"
        return "sqlite"

    @property
    def app_version(self) -> str:
        return (os.environ.get("APP_VERSION") or os.environ.get("FIRESCRAPLING_VERSION") or "dev").strip()

    @property
    def git_commit(self) -> str:
        return (os.environ.get("GIT_COMMIT") or os.environ.get("SOURCE_COMMIT") or "").strip() or "unknown"

    def platform_env_info(self) -> Optional[dict]:
        """Which env-configured provider key is present (for Operators UI). Prefer Scrape.do."""
        if self.scrapedo_configured:
            return {"provider": "scrapedo", "env_var": "SCRAPE_API_KEY"}
        if self.scrapfly_configured:
            return {"provider": "scrapfly", "env_var": "SCRAPFLY_API_KEY"}
        return None

    @property
    def credential_encryption_key(self) -> str:
        """Primary Fernet key (alias of first entry in CREDENTIAL_ENCRYPTION_KEYS)."""
        keys = self.credential_encryption_keys
        return keys[0] if keys else ""

    @property
    def credential_encryption_keys(self) -> list[str]:
        """Fernet keys newest-first. CREDENTIAL_ENCRYPTION_KEYS or single KEY."""
        multi = (os.environ.get("CREDENTIAL_ENCRYPTION_KEYS") or "").strip()
        if multi:
            return [k.strip() for k in multi.split(",") if k.strip()]
        single = (os.environ.get("CREDENTIAL_ENCRYPTION_KEY") or "").strip()
        return [single] if single else []

    def validate_startup(self) -> None:
        """Fail closed when BYOK is on without a Fernet key."""
        if self.byok_enabled and not self.credential_encryption_keys:
            raise RuntimeError(
                "BYOK_ENABLED=true requires CREDENTIAL_ENCRYPTION_KEY "
                '(or CREDENTIAL_ENCRYPTION_KEYS, newest first) '
                '(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")'
            )

    @property
    def crawl_global_concurrency(self) -> int:
        try:
            return max(1, int(os.environ.get("CRAWL_GLOBAL_CONCURRENCY") or "4"))
        except ValueError:
            return 4

    @property
    def crawl_per_host_concurrency(self) -> int:
        try:
            return max(1, int(os.environ.get("CRAWL_PER_HOST_CONCURRENCY") or "2"))
        except ValueError:
            return 2

    @property
    def stripe_secret_key(self) -> str:
        return (os.environ.get("STRIPE_SECRET_KEY") or "").strip()

    @property
    def stripe_webhook_secret(self) -> str:
        return (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()

    def resolved_provider(self) -> Literal["scrapfly", "scrapedo", "local"]:
        mode = self.fetch_provider
        if mode == "local":
            return "local"
        if mode == "scrapfly":
            return "scrapfly"
        if mode == "scrapedo":
            return "scrapedo"
        if not self.managed_fetch_enabled:
            return "local"
        # auto: prefer Scrape.do (cheaper in bake-off), then Scrapfly, else local.
        if self.scrapedo_configured:
            return "scrapedo"
        if self.scrapfly_configured:
            return "scrapfly"
        return "local"

    def capabilities(self) -> dict:
        provider = self.resolved_provider()
        queue_ok = False
        if self.queue_enabled:
            try:
                import redis

                r = redis.from_url(self.redis_url, socket_connect_timeout=0.5)
                r.ping()
                queue_ok = True
            except Exception:
                queue_ok = False
        paid = provider in ("scrapfly", "scrapedo") and self.managed_fetch_enabled
        return {
            "scrapfly": self.scrapfly_configured and self.managed_fetch_enabled,
            "scrapedo": self.scrapedo_configured and self.managed_fetch_enabled,
            "fetch_provider": provider if self.managed_fetch_enabled else "local",
            "fetch_escalate": self.fetch_escalate,
            "js_render": True,
            "js_render_default": paid and self.scrapfly_default_render_js,
            "anti_bot": paid and self.scrapfly_default_asp,
            "proxy_rotation": paid,
            "queue": queue_ok,
            "webhooks": True,
            "markdown": True,
            "byok": self.byok_enabled,
            "hosted": self.hosted_mode,
            "managed_fetch": self.managed_fetch_enabled,
            "encryption_key_present": bool(self.credential_encryption_keys),
            "admin_configured": self.admin_configured,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "domain_profile_ttl_seconds": self.fetch_profile_ttl_seconds,
            "database_backend": self.database_backend,
            "worker_concurrency": self.worker_concurrency,
            "version": self.app_version,
            "commit": self.git_commit,
            "platform_env": self.platform_env_info(),
            "crawl_global_concurrency": self.crawl_global_concurrency,
            "crawl_per_host_concurrency": self.crawl_per_host_concurrency,
            "billing": bool(self.stripe_secret_key) and self.hosted_mode,
            "extract_media": True,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
