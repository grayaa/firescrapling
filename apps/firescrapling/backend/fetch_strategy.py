"""Credit-aware fetch: classify page needs, escalate tiers, cache per-domain profiles."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple, TYPE_CHECKING
from urllib.parse import urlparse

from fetch_provider import FetchError, FetchResult, LocalFetcher, ScrapedoFetcher, ScrapflyFetcher
from settings import get_settings

if TYPE_CHECKING:
    from fetch_context import FetchContext

logger = logging.getLogger(__name__)

ClassifyResult = Literal["ok", "needs_js", "bot_wall", "soft_fail", "terminal"]

TIER_ORDER: List[str] = ["local", "sf_static", "sf_js", "sf_asp", "sf_residential"]

_CF_MARKERS = (
    "just a moment",
    "cf-browser-verification",
    "challenge-platform",
    "cdn-cgi/challenge",
    "checking your browser",
    "attention required",
    "enable javascript and cookies to continue",
)
_JS_HINTS = (
    "enable javascript",
    "javascript is required",
    "you need to enable javascript",
    "noscript",
)
_SPA_MARKERS = (
    'id="__next"',
    "id='__next'",
    'id="root"',
    "id='root'",
    'id="app"',
    "__NEXT_DATA__",
    "ng-version",
    "data-reactroot",
)

# In-process fallback when Redis is unavailable (tests / single process).
_memory_profiles: Dict[str, Tuple[float, Dict[str, Any]]] = {}


@dataclass
class TierSpec:
    name: str
    use_local: bool
    render_js: bool = False
    asp: bool = False
    proxy_pool: Optional[str] = None


@dataclass
class StrategyFetchResult(FetchResult):
    """FetchResult plus which ladder tier succeeded."""

    fetch_tier: str = "unknown"
    escalated: bool = False
    attempts: List[str] = field(default_factory=list)
    profile_hit: bool = False
    domain: str = ""


def registrable_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or "unknown"


def tier_specs(ctx: Optional["FetchContext"] = None) -> Dict[str, TierSpec]:
    if ctx is not None:
        dc = ctx.paid_pool(residential=False)
        res = ctx.paid_pool(residential=True)
    else:
        settings = get_settings()
        dc = settings.scrapfly_proxy_pool or "public_datacenter_pool"
        if "residential" in dc.lower():
            dc = "public_datacenter_pool"
        res = settings.scrapfly_residential_pool
    return {
        "local": TierSpec("local", use_local=True),
        "sf_static": TierSpec("sf_static", use_local=False, render_js=False, asp=False, proxy_pool=dc),
        "sf_js": TierSpec("sf_js", use_local=False, render_js=True, asp=False, proxy_pool=dc),
        "sf_asp": TierSpec("sf_asp", use_local=False, render_js=True, asp=True, proxy_pool=dc),
        "sf_residential": TierSpec(
            "sf_residential", use_local=False, render_js=True, asp=True, proxy_pool=res
        ),
    }


def classify_fetch(
    html: str,
    status: Optional[int],
    error: Optional[BaseException] = None,
) -> ClassifyResult:
    """Decide whether content is usable or what escalation is needed."""
    if error is not None:
        if isinstance(error, FetchError) and error.code in (
            "upstream_blocked",
            "scrapfly_error",
            "scrapedo_error",
        ):
            if error.status in (403, 429) or error.code == "upstream_blocked":
                return "bot_wall"
            if error.status >= 500:
                return "soft_fail"
            return "bot_wall"
        msg = str(error).lower()
        if any(
            x in msg
            for x in (
                "timeout",
                "timed out",
                "connection",
                "could not connect",
                "failed to connect",
                "name or service not known",
                "nodename nor servname",
                "network is unreachable",
            )
        ):
            return "soft_fail"
        if "403" in msg or "forbidden" in msg or "cloudflare" in msg:
            return "bot_wall"
        return "soft_fail"

    st = int(status or 0)
    if st in (404, 410, 451):
        return "terminal"
    if st in (403, 401, 429):
        return "bot_wall"
    if st >= 500:
        return "soft_fail"
    # A 4xx that is not a known bot signal is a client error. No tier can fix it.
    if 400 <= st < 500 and st not in (401, 403, 429):
        return "terminal"

    text = html or ""
    low = text.lower()
    if any(m in low for m in _CF_MARKERS) and (
        "cloudflare" in low or "cf-" in low or "just a moment" in low
    ):
        return "bot_wall"

    # Strip tags lightly for text density
    stripped = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    stripped = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", stripped)
    stripped = re.sub(r"(?is)<[^>]+>", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    text_len = len(stripped)
    html_len = len(text)

    spa = any(m.lower() in low for m in _SPA_MARKERS)
    js_hint = any(h in low for h in _JS_HINTS)

    if st < 400 and text_len >= 120:
        return "ok"
    if st < 400 and text_len >= 40 and not spa and not js_hint:
        return "ok"
    if spa or js_hint or (html_len < 2500 and text_len < 80):
        return "needs_js"
    if st < 400 and text_len >= 40:
        return "ok"
    return "needs_js"


def _profile_key(domain: str) -> str:
    return f"fs:fetch-profile:{domain}"


def get_domain_profile(domain: str) -> Optional[Dict[str, Any]]:
    settings = get_settings()
    ttl = settings.fetch_profile_ttl_seconds
    # Memory first (also used when Redis write succeeded — keep warm)
    mem = _memory_profiles.get(domain)
    if mem:
        expires, payload = mem
        if time.time() < expires:
            return dict(payload)
        _memory_profiles.pop(domain, None)

    try:
        import redis

        r = redis.from_url(settings.redis_url, socket_connect_timeout=0.4)
        raw = r.get(_profile_key(domain))
        if raw:
            data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            if isinstance(data, dict) and data.get("tier") in TIER_ORDER:
                _memory_profiles[domain] = (time.time() + ttl, data)
                return data
    except Exception:
        pass
    return None


def set_domain_profile(domain: str, tier: str, spec: TierSpec) -> None:
    settings = get_settings()
    ttl = settings.fetch_profile_ttl_seconds
    payload = {
        "tier": tier,
        "render_js": spec.render_js,
        "asp": spec.asp,
        "proxy_pool": spec.proxy_pool,
        "updated_at": time.time(),
    }
    _memory_profiles[domain] = (time.time() + ttl, payload)
    try:
        import redis

        r = redis.from_url(settings.redis_url, socket_connect_timeout=0.4)
        r.set(_profile_key(domain), json.dumps(payload), ex=ttl)
    except Exception:
        pass


def clear_memory_profiles() -> None:
    _memory_profiles.clear()


def clear_all_profiles() -> None:
    """Drop in-memory and Redis domain profiles (tests / admin)."""
    clear_memory_profiles()
    try:
        import redis
        from settings import get_settings

        r = redis.from_url(get_settings().redis_url, socket_connect_timeout=0.4)
        for key in r.scan_iter(match="fs:fetch-profile:*", count=100):
            r.delete(key)
    except Exception:
        pass


def _next_tier_for(verdict: ClassifyResult, current: str, has_paid: bool) -> Optional[str]:
    if verdict in ("ok", "terminal"):
        return None
    if not has_paid:
        return None
    idx = TIER_ORDER.index(current) if current in TIER_ORDER else 0
    if verdict == "soft_fail":
        # Jump at least to sf_static
        target = "sf_static"
    elif verdict == "needs_js":
        target = "sf_js"
    elif verdict == "bot_wall":
        target = "sf_asp" if current != "sf_asp" else "sf_residential"
        if current == "sf_residential":
            return None
    else:
        return None
    t_idx = TIER_ORDER.index(target)
    # Always move forward at least one step
    next_idx = max(idx + 1, t_idx)
    if next_idx >= len(TIER_ORDER):
        return None
    return TIER_ORDER[next_idx]


def _paid_allowed_for(url: str) -> bool:
    """Paid providers cannot reach private hosts — and must not be told about them."""
    from security_url import is_private_host

    try:
        return not is_private_host(url)
    except Exception:
        return False  # fail closed


def _paid_fetcher(ctx: Optional["FetchContext"] = None):
    """Cloud fetcher for escalate tiers — prefers ctx, else process settings."""
    if ctx is not None:
        if not ctx.can_use_paid:
            return None
        if ctx.provider == "scrapedo":
            return ScrapedoFetcher(ctx.api_key or "")
        if ctx.provider == "scrapfly":
            return ScrapflyFetcher(ctx.api_key or "")
        return None
    settings = get_settings()
    provider = settings.resolved_provider()
    if provider == "local":
        if settings.scrapedo_configured:
            return ScrapedoFetcher(settings.scrapedo_api_key)
        if settings.scrapfly_configured:
            return ScrapflyFetcher(settings.scrapfly_api_key)
        return None
    if provider == "scrapedo":
        return ScrapedoFetcher(settings.scrapedo_api_key)
    if provider == "scrapfly":
        return ScrapflyFetcher(settings.scrapfly_api_key)
    return None


def _run_tier(
    url: str,
    spec: TierSpec,
    *,
    timeout: int,
    country: Optional[str],
    ctx: Optional["FetchContext"] = None,
) -> Tuple[Optional[FetchResult], Optional[BaseException]]:
    try:
        if spec.use_local:
            result = LocalFetcher().fetch(url, timeout=timeout)
        else:
            fetcher = _paid_fetcher(ctx)
            if fetcher is None:
                return None, FetchError(
                    "No paid fetch provider configured",
                    code="fetch_unconfigured",
                    status=503,
                )
            result = fetcher.fetch(
                url,
                timeout=timeout,
                render_js=spec.render_js,
                asp=spec.asp,
                proxy_pool=spec.proxy_pool,
                country=country,
            )
        return result, None
    except Exception as e:
        return None, e


def fetch_with_strategy(
    url: str,
    *,
    timeout: int = 30,
    render_js: Optional[bool] = None,
    asp: Optional[bool] = None,
    proxy_pool: Optional[str] = None,
    country: Optional[str] = None,
    ctx: Optional["FetchContext"] = None,
) -> StrategyFetchResult:
    """
    Cheap-first escalate unless the client set renderJs/asp/proxyPool, or FETCH_ESCALATE=false.
    """
    settings = get_settings()
    explicit = render_js is not None or asp is not None or proxy_pool is not None
    escalate = settings.fetch_escalate and not explicit
    paid_ok = _paid_allowed_for(url)
    if ctx is not None:
        country_final = country if country is not None else ctx.country
        has_paid = bool(ctx.can_use_paid) and paid_ok
        provider_name = ctx.provider
        specs = tier_specs(ctx)
    else:
        country_final = country if country is not None else settings.scrapfly_country
        has_paid = bool(settings.paid_fetch_configured) and paid_ok
        provider_name = settings.resolved_provider()
        specs = tier_specs()

    if not paid_ok and (
        (ctx is not None and ctx.can_use_paid) or settings.paid_fetch_configured
    ):
        logger.info(
            "fetch_strategy domain=%s provider=local tier=guard verdict=private_host status=None",
            registrable_domain(url),
        )

    if not escalate:
        # Single-shot: defaults + explicit overrides
        from fetch_provider import LocalFetcher, default_fetch_options, get_fetcher

        opts = default_fetch_options(ctx if has_paid else None)
        if render_js is not None:
            opts["render_js"] = render_js
        if asp is not None:
            opts["asp"] = asp
        if proxy_pool is not None:
            opts["proxy_pool"] = proxy_pool
        if country is not None:
            opts["country"] = country
        # Never hand private/loopback URLs to a paid provider.
        fetcher = LocalFetcher() if not paid_ok else get_fetcher(ctx)
        result = fetcher.fetch(
            url,
            timeout=timeout,
            render_js=bool(opts.get("render_js")),
            asp=bool(opts.get("asp")),
            proxy_pool=opts.get("proxy_pool"),
            country=opts.get("country"),
        )
        tier = "explicit" if explicit else "default"
        return StrategyFetchResult(
            html_content=result.html_content,
            url=result.url,
            status=result.status,
            fetch_tier=tier,
            escalated=False,
            attempts=[tier],
            profile_hit=False,
            domain=registrable_domain(url),
        )

    domain = registrable_domain(url)
    cached = get_domain_profile(domain)
    start_tier = "local"
    profile_hit = False
    if cached and cached.get("tier") in TIER_ORDER:
        start_tier = str(cached["tier"])
        profile_hit = start_tier != "local"
        if start_tier != "local" and not has_paid:
            start_tier = "local"
            profile_hit = False

    attempts: List[str] = []
    current = start_tier
    last_result: Optional[FetchResult] = None
    last_error: Optional[BaseException] = None
    started_at = start_tier
    if provider_name == "local" and has_paid and ctx is None:
        provider_name = "scrapedo" if settings.scrapedo_configured else "scrapfly"

    for _ in range(len(TIER_ORDER)):
        if current not in specs:
            break
        if current != "local" and not has_paid:
            break
        attempts.append(current)
        spec = specs[current]
        result, err = _run_tier(
            url, spec, timeout=timeout, country=country_final, ctx=ctx
        )
        last_result, last_error = result, err
        status = result.status if result else (getattr(err, "status", None) if isinstance(err, FetchError) else None)
        html = result.html_content if result else ""
        verdict = classify_fetch(html, status, err)
        logger.info(
            "fetch_strategy domain=%s provider=%s tier=%s verdict=%s status=%s",
            domain,
            provider_name if current != "local" else "local",
            current,
            verdict,
            status,
        )

        if verdict == "ok" and result is not None:
            set_domain_profile(domain, current, spec)
            return StrategyFetchResult(
                html_content=result.html_content,
                url=result.url,
                status=result.status,
                fetch_tier=current,
                escalated=current != started_at or len(attempts) > 1,
                attempts=attempts,
                profile_hit=profile_hit and len(attempts) == 1,
                domain=domain,
            )

        if verdict == "terminal" and result is not None:
            return StrategyFetchResult(
                html_content=result.html_content,
                url=result.url,
                status=result.status,
                fetch_tier=current,
                escalated=len(attempts) > 1,
                attempts=attempts,
                profile_hit=False,
                domain=domain,
            )

        nxt = _next_tier_for(verdict, current, has_paid)
        if not nxt or nxt == current:
            break
        current = nxt

    if last_error is not None:
        if isinstance(last_error, FetchError):
            raise last_error
        raise FetchError(str(last_error), code="fetch_error", status=502) from last_error
    if last_result is not None:
        return StrategyFetchResult(
            html_content=last_result.html_content,
            url=last_result.url,
            status=last_result.status,
            fetch_tier=attempts[-1] if attempts else "unknown",
            escalated=len(attempts) > 1,
            attempts=attempts,
            profile_hit=False,
            domain=domain,
        )
    raise FetchError("fetch_with_strategy: no result", code="fetch_error", status=502)
