"""Pluggable URL fetch: local scrapling, Scrapfly, or Scrape.do."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Protocol

if TYPE_CHECKING:
    from fetch_context import FetchContext

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Normalized fetch response — mirrors scrapling Response attrs used in the codebase."""

    html_content: str
    url: str
    status: int


class FetchError(Exception):
    def __init__(self, message: str, *, code: str = "fetch_error", status: int = 502):
        self.code = code
        self.status = status
        super().__init__(message)


class FetcherProtocol(Protocol):
    def fetch(
        self,
        url: str,
        *,
        timeout: int = 30,
        render_js: bool = False,
        asp: bool = False,
        proxy_pool: Optional[str] = None,
        country: Optional[str] = None,
    ) -> FetchResult: ...


class LocalFetcher:
    def fetch(
        self,
        url: str,
        *,
        timeout: int = 30,
        render_js: bool = False,
        asp: bool = False,
        proxy_pool: Optional[str] = None,
        country: Optional[str] = None,
    ) -> FetchResult:
        # Local path ignores cloud-provider flags (render_js/asp/proxy).
        from scrapling import Fetcher

        response = Fetcher.get(url, timeout=timeout)
        status = int(getattr(response, "status", None) or 200)
        html = getattr(response, "html_content", None) or ""
        final = getattr(response, "url", None) or url
        return FetchResult(html_content=html, url=str(final), status=status)


class ScrapflyFetcher:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def fetch(
        self,
        url: str,
        *,
        timeout: int = 30,
        render_js: bool = False,
        asp: bool = False,
        proxy_pool: Optional[str] = None,
        country: Optional[str] = None,
    ) -> FetchResult:
        try:
            from scrapfly import ScrapeApiResponse, ScrapeConfig, ScrapflyClient
        except ImportError as e:
            raise FetchError(
                "scrapfly-sdk is not installed",
                code="scrapfly_unavailable",
                status=503,
            ) from e

        pool = proxy_pool or "public_datacenter_pool"
        # ASP needs retries to upgrade proxy/browser; static scrapes stay cheaper without retry.
        use_retry = bool(asp)
        cfg_kwargs: dict = {
            "url": url,
            "render_js": render_js,
            "asp": asp,
            "retry": use_retry,
            "raise_on_upstream_error": False,
        }
        if pool:
            cfg_kwargs["proxy_pool"] = pool
        if country:
            cfg_kwargs["country"] = country
        if render_js:
            cfg_kwargs["rendering_wait"] = 3000
        # Scrapfly forbids custom timeout when retry=True.
        if not use_retry:
            cfg_kwargs["timeout"] = max(timeout * 1000, 30000)

        client = ScrapflyClient(key=self._api_key)
        try:
            api_response: ScrapeApiResponse = client.scrape(ScrapeConfig(**cfg_kwargs))
        except Exception as e:
            name = type(e).__name__
            if "Asp" in name or "asp" in str(e).lower():
                raise FetchError(str(e), code="upstream_blocked", status=403) from e
            raise FetchError(str(e), code="scrapfly_error", status=502) from e

        result = getattr(api_response, "scrape_result", None) or {}
        if not isinstance(result, dict):
            result = {}
        content = result.get("content") or ""
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        status = int(result.get("status_code") or getattr(api_response, "upstream_status_code", None) or 200)
        final_url = (
            result.get("url")
            or (result.get("config") or {}).get("url")
            or url
        )
        # Cloudflare interstitial still counts as blocked even if HTML was returned.
        low = str(content).lower()
        if status == 403 or ("just a moment" in low and "cloudflare" in low):
            raise FetchError(
                "Upstream anti-bot challenge not cleared",
                code="upstream_blocked",
                status=403,
            )
        return FetchResult(html_content=str(content), url=str(final_url), status=status)


class ScrapedoFetcher:
    """Scrape.do Web Scraping API — https://scrape.do/documentation/"""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def fetch(
        self,
        url: str,
        *,
        timeout: int = 30,
        render_js: bool = False,
        asp: bool = False,
        proxy_pool: Optional[str] = None,
        country: Optional[str] = None,
    ) -> FetchResult:
        import requests

        pool = (proxy_pool or "").lower()
        # Map our flags: asp / residential → super (residential+mobile); render_js → render.
        use_super = bool(asp) or "residential" in pool
        params: dict = {"token": self._api_key, "url": url}
        if render_js:
            params["render"] = "true"
        if use_super:
            params["super"] = "true"
        if country:
            params["geoCode"] = country

        try:
            # Hard tiers need headroom; Scrape.do default timeout is 60s.
            http_timeout = max(timeout, 90 if use_super or render_js else 45)
            resp = requests.get("https://api.scrape.do/", params=params, timeout=http_timeout)
        except requests.RequestException as e:
            raise FetchError(str(e), code="scrapedo_error", status=502) from e

        content = resp.text or ""
        status = int(resp.status_code)

        if status == 401:
            raise FetchError(
                "Scrape.do API token rejected",
                code="scrapedo_unconfigured",
                status=401,
            )
        if status == 429:
            raise FetchError(
                "Scrape.do rate/concurrency limit",
                code="scrapedo_error",
                status=429,
            )
        # Gateway JSON errors (e.g. 502 ErrorCode 90) — treat as soft/hard fail upstream.
        if status >= 500:
            raise FetchError(
                content[:300] or f"Scrape.do HTTP {status}",
                code="scrapedo_error",
                status=status,
            )

        low = content.lower()
        if status == 403 or ("just a moment" in low and "cloudflare" in low):
            raise FetchError(
                "Upstream anti-bot challenge not cleared",
                code="upstream_blocked",
                status=403,
            )
        return FetchResult(html_content=str(content), url=url, status=status)


def get_fetcher(ctx: Optional["FetchContext"] = None) -> FetcherProtocol:
    if ctx is not None:
        if ctx.provider == "scrapedo" and ctx.api_key:
            return ScrapedoFetcher(ctx.api_key)
        if ctx.provider == "scrapfly" and ctx.api_key:
            return ScrapflyFetcher(ctx.api_key)
        return LocalFetcher()

    from settings import get_settings

    settings = get_settings()
    provider = settings.resolved_provider()
    if provider == "scrapedo":
        if not settings.scrapedo_api_key:
            raise FetchError(
                "FETCH_PROVIDER=scrapedo but SCRAPE_API_KEY is unset",
                code="scrapedo_unconfigured",
                status=503,
            )
        return ScrapedoFetcher(settings.scrapedo_api_key)
    if provider == "scrapfly":
        if not settings.scrapfly_api_key:
            raise FetchError(
                "FETCH_PROVIDER=scrapfly but SCRAPFLY_API_KEY is unset",
                code="scrapfly_unconfigured",
                status=503,
            )
        return ScrapflyFetcher(settings.scrapfly_api_key)
    return LocalFetcher()


def default_fetch_options(ctx: Optional["FetchContext"] = None) -> dict:
    """Defaults for scrape/crawl when caller omits render/asp/pool."""
    from settings import get_settings

    settings = get_settings()
    if ctx is not None:
        if ctx.can_use_paid:
            return {
                "render_js": settings.scrapfly_default_render_js,
                "asp": settings.scrapfly_default_asp,
                "proxy_pool": ctx.proxy_pool if ctx.provider == "scrapfly" else None,
                "country": ctx.country,
            }
        return {
            "render_js": False,
            "asp": False,
            "proxy_pool": None,
            "country": None,
        }

    provider = settings.resolved_provider()
    if provider in ("scrapfly", "scrapedo"):
        return {
            "render_js": settings.scrapfly_default_render_js,
            "asp": settings.scrapfly_default_asp,
            "proxy_pool": settings.scrapfly_proxy_pool if provider == "scrapfly" else None,
            "country": settings.scrapfly_country,
        }
    return {
        "render_js": False,
        "asp": False,
        "proxy_pool": None,
        "country": None,
    }
