"""HTTP API for FireScrapling (FastAPI)."""
from __future__ import annotations

import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any, Dict, Iterator, List, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

import main as core
from api_auth import (
    ApiContext,
    check_playground_rate_limit,
    get_account_user_id,
    get_admin_context,
    get_api_context,
    get_session_user,
    require_auth_enabled,
)
from security_url import validate_request_url

RATE_LIMIT_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))

_PLAYGROUND_MAP_MAX = int(os.environ.get("PLAYGROUND_MAP_MAX_LINKS", "40"))
_PLAYGROUND_CRAWL_LIMIT = int(os.environ.get("PLAYGROUND_CRAWL_LIMIT", "3"))
_PLAYGROUND_PREVIEW_CHARS = int(os.environ.get("PLAYGROUND_RESULT_PREVIEW_CHARS", "12000"))


@asynccontextmanager
async def _lifespan(application: FastAPI):  # noqa: ARG001
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    core.configure_logging(log_level)
    try:
        from preflight import run_preflight

        run_preflight()
    except Exception:
        import logging

        logging.getLogger(__name__).exception("preflight skipped")
    core.init_db()
    try:
        from job_queue import recover_orphaned_jobs

        n = recover_orphaned_jobs()
        if n:
            import logging

            logging.getLogger(__name__).info("recovered %s orphaned jobs", n)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("orphaned job recovery skipped")
    yield


app = FastAPI(title="FireScrapling API", version="1.0.0", lifespan=_lifespan)

_origins = os.environ.get("CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


app.add_middleware(RequestIdMiddleware)

from routers.billing import router as _billing_router

app.include_router(_billing_router)


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    d = exc.detail
    if isinstance(d, dict):
        code = str(d.get("code", f"http_{exc.status_code}"))
        msg = d.get("message", str(d))
    else:
        code = f"http_{exc.status_code}"
        msg = str(d)
    hdrs: Dict[str, str] = {"X-Request-ID": rid}
    exc_headers = getattr(exc, "headers", None)
    if exc_headers:
        hdrs.update({str(k): str(v) for k, v in exc_headers.items()})
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": msg, "request_id": rid}},
        headers=hdrs,
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": exc.errors(), "request_id": rid}},
        headers={"X-Request-ID": rid},
    )


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": str(exc), "request_id": rid}},
        headers={"X-Request-ID": rid},
    )


def _rate_headers(response: Response, ctx: ApiContext) -> None:
    response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_LIMIT)
    response.headers["X-RateLimit-Remaining"] = str(ctx.rate_limit_remaining)
    response.headers["X-RateLimit-Reset"] = str(ctx.rate_limit_reset)


def _job_for_context(ctx: ApiContext, job_id: str) -> Optional[Dict[str, Any]]:
    if ctx.user_id:
        return core.get_job_for_user(job_id, ctx.user_id)
    return core.get_job_by_id(job_id)


def _check_target_url(url: str) -> None:
    err = validate_request_url(url)
    if err:
        raise HTTPException(status_code=400, detail={"code": "invalid_url", "message": err})


def _ensure_webhook_secret(webhook: Optional[str], secret: Optional[str]) -> tuple[Optional[str], Optional[str], bool]:
    """Returns (url, secret, generated_secret)."""
    if not webhook or not str(webhook).strip():
        return None, None, False
    w = str(webhook).strip()
    if secret and str(secret).strip():
        return w, str(secret).strip(), False
    return w, secrets.token_hex(32), True


class ScrapeRequest(BaseModel):
    url: str
    formats: List[str] = Field(default=["markdown"])
    onlyMainContent: bool = True
    actions: Optional[List[Dict[str, Any]]] = None
    schema_: Optional[Dict[str, Any]] = Field(default=None, validation_alias="schema")
    async_mode: bool = Field(default=False, alias="async")
    webhook: Optional[str] = None
    webhook_secret: Optional[str] = None
    renderJs: Optional[bool] = None
    asp: Optional[bool] = None
    proxyPool: Optional[str] = None
    country: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("url")
    @classmethod
    def url_nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("url is required")
        return str(v).strip()


class CrawlRequest(BaseModel):
    url: str
    limit: int = 100
    maxDepth: int = 2
    ignoreSubdomains: bool = False
    webhook: Optional[str] = None
    webhook_secret: Optional[str] = None
    renderJs: Optional[bool] = None
    asp: Optional[bool] = None
    proxyPool: Optional[str] = None
    country: Optional[str] = None

    @field_validator("url")
    @classmethod
    def url_nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("url is required")
        return str(v).strip()


class MapRequest(BaseModel):
    url: str
    search: Optional[str] = None
    ignoreSubdomains: bool = False

    @field_validator("url")
    @classmethod
    def url_nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("url is required")
        return str(v).strip()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    full_name: Optional[str] = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class CreateKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PlaygroundUrlBody(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def playground_url_nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("url is required")
        return str(v).strip()


class PlaygroundMapBody(BaseModel):
    url: str
    search: Optional[str] = None
    ignoreSubdomains: bool = False

    @field_validator("url")
    @classmethod
    def playground_map_url_nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("url is required")
        return str(v).strip()


class ExtractMediaRequest(BaseModel):
    url: str
    renderJs: Optional[bool] = None

    @field_validator("url")
    @classmethod
    def extract_url_nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("url is required")
        return str(v).strip()


class CheckoutRequest(BaseModel):
    """Kept for OpenAPI compatibility when hosted; billing router owns the live schema."""
    plan: str = Field(description="pro or team")
    success_url: str
    cancel_url: str

    @field_validator("plan")
    @classmethod
    def plan_ok(cls, v: str) -> str:
        p = (v or "").strip().lower()
        if p not in ("pro", "team"):
            raise ValueError("plan must be 'pro' or 'team'")
        return p


def _playground_rate_headers(response: Response, rem: int, reset: int, lim: int) -> None:
    response.headers["X-RateLimit-Limit"] = str(lim)
    response.headers["X-RateLimit-Remaining"] = str(rem)
    response.headers["X-RateLimit-Reset"] = str(reset)


def _truncate_playground_scrape_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    lim = _PLAYGROUND_PREVIEW_CHARS
    md = out.get("markdown")
    if isinstance(md, str) and len(md) > lim:
        out["markdown"] = md[:lim] + "\n\n[truncated for playground preview]"
    raw = out.get("raw")
    if isinstance(raw, dict):
        rmd = raw.get("markdown")
        if isinstance(rmd, str) and len(rmd) > lim:
            raw = dict(raw)
            raw["markdown"] = rmd[:lim] + "\n\n[truncated for playground preview]"
            out["raw"] = raw
    return out


def _truncate_crawl_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lim = _PLAYGROUND_PREVIEW_CHARS
    out: List[Dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        md = r.get("markdown")
        if isinstance(md, str) and len(md) > lim:
            r["markdown"] = md[:lim] + "\n\n[truncated for playground preview]"
        out.append(r)
    return out


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


class PlatformEnvInfo(BaseModel):
    provider: Literal["scrapedo", "scrapfly"]
    env_var: str


class CapabilitiesResponse(BaseModel):
    """Typed /v1/capabilities contract — dashboard and docs branch on these flags."""

    model_config = ConfigDict(extra="allow")

    scrapfly: bool = False
    scrapedo: bool = False
    fetch_provider: str = "local"
    fetch_escalate: bool = True
    js_render: bool = True
    js_render_default: bool = False
    anti_bot: bool = False
    proxy_rotation: bool = False
    queue: bool = False
    webhooks: bool = True
    markdown: bool = True
    byok: bool = False
    hosted: bool = False
    managed_fetch: bool = True
    playground: bool = False
    registration_open: bool = False
    billing: bool = False
    extract_media: bool = True
    encryption_key_present: bool = False
    admin_configured: bool = False
    rate_limit_per_minute: int = 60
    domain_profile_ttl_seconds: int = 86400
    database_backend: str = "sqlite"
    worker_concurrency: int = 2
    version: str = "dev"
    commit: str = "unknown"
    credential_source: Optional[str] = None
    credential_provider: Optional[str] = None
    platform_env: Optional[PlatformEnvInfo] = None
    crawl_global_concurrency: Optional[int] = None
    crawl_per_host_concurrency: Optional[int] = None


@app.get("/v1/capabilities", response_model=CapabilitiesResponse)
def capabilities(
    authorization: Annotated[Optional[str], Header()] = None,
) -> CapabilitiesResponse:
    """Public flags describing which optional infra is configured."""
    from settings import get_settings
    from provider_credentials import build_fetch_context
    from api_auth import playground_enabled

    settings = get_settings()
    caps = settings.capabilities()
    caps["registration_open"] = core.registration_is_open()
    caps["playground"] = playground_enabled()

    user_id = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            try:
                user_id = core.resolve_session_token(parts[1].strip())
            except Exception:
                user_id = None
    try:
        ctx = build_fetch_context(user_id)
        caps["credential_source"] = ctx.source
        caps["credential_provider"] = ctx.provider
    except Exception as e:
        from provider_credentials import CredentialUndecryptable

        if isinstance(e, CredentialUndecryptable):
            caps["credential_source"] = "undecryptable"
        else:
            caps["credential_source"] = "local"
            caps["credential_provider"] = "local"
    return CapabilitiesResponse(**caps)


class ProviderCreateRequest(BaseModel):
    provider: str = Field(..., pattern="^(scrapedo|scrapfly)$")
    api_key: str = Field(..., min_length=8, max_length=512)
    label: Optional[str] = Field(None, max_length=120)
    country: Optional[str] = Field(None, max_length=8)
    proxy_pool: Optional[str] = None
    residential_pool: Optional[str] = None


@app.get("/v1/providers")
def providers_list(user_id: str = Depends(get_session_user)) -> Dict[str, Any]:
    from provider_credentials import list_provider_credentials

    return {"success": True, "providers": list_provider_credentials(user_id)}


@app.post("/v1/providers")
def providers_create(
    req: ProviderCreateRequest,
    user_id: str = Depends(get_session_user),
) -> Dict[str, Any]:
    from provider_credentials import create_provider_credential
    from settings import get_settings

    if not get_settings().byok_enabled:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "byok_disabled",
                "message": "BYOK is disabled (set BYOK_ENABLED=true and CREDENTIAL_ENCRYPTION_KEY)",
            },
        )
    try:
        row = create_provider_credential(
            user_id,
            req.provider,  # type: ignore[arg-type]
            req.api_key,
            label=req.label,
            country=req.country,
            proxy_pool=req.proxy_pool,
            residential_pool=req.residential_pool,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "invalid_provider", "message": str(e)}) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail={"code": "encryption_unavailable", "message": str(e)}) from e
    return {"success": True, "provider": row}


@app.post("/v1/providers/{credential_id}/verify")
def providers_verify(
    credential_id: str,
    user_id: str = Depends(get_session_user),
) -> Dict[str, Any]:
    from provider_credentials import CredentialUndecryptable, verify_credential_live

    try:
        out = verify_credential_live(user_id, credential_id)
    except LookupError:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Credential not found"})
    except CredentialUndecryptable as e:
        raise HTTPException(
            status_code=503,
            detail={"code": "credential_undecryptable", "message": str(e)},
        ) from e
    return {"success": True, **out}


@app.delete("/v1/providers/{credential_id}")
def providers_delete(
    credential_id: str,
    user_id: str = Depends(get_session_user),
) -> Dict[str, Any]:
    from provider_credentials import delete_provider_credential

    if not delete_provider_credential(user_id, credential_id):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Credential not found"})
    return {"success": True}


@app.get("/health/ready")
def health_ready() -> Dict[str, Any]:
    try:
        conn = core._get_db()
        conn.execute("SELECT 1")
        conn.close()
        return {"status": "ready", "database": "ok"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"code": "not_ready", "message": str(e)},
        )


@app.post("/v1/playground/scrape")
def playground_scrape(request: Request, response: Response, body: PlaygroundUrlBody) -> Dict[str, Any]:
    """Anonymous homepage demo: markdown-only scrape, strict URL checks, IP rate limit."""
    _, rem, reset, lim = check_playground_rate_limit(request)
    _playground_rate_headers(response, rem, reset, lim)
    err = validate_request_url(body.url, force_public_only=True)
    if err:
        raise HTTPException(status_code=400, detail={"code": "invalid_url", "message": err})
    result: Optional[Dict[str, Any]] = None
    last_err: Optional[str] = None
    for event in core.scrape_page_streaming(
        url=body.url,
        user_id=None,
        key_id=None,
        formats=["markdown"],
        onlyMainContent=True,
        actions=None,
        schema=None,
        webhook_url=None,
        webhook_secret=None,
        usage_endpoint="/v1/playground/scrape",
    ):
        et = event.get("type")
        if et == "result":
            result = event.get("data")
        elif et == "error":
            last_err = str(event.get("content", "Unknown error"))
    if last_err:
        raise HTTPException(status_code=500, detail={"code": "scrape_failed", "message": last_err})
    if not result:
        raise HTTPException(status_code=500, detail={"code": "scrape_failed", "message": "No result"})
    return {"success": True, "data": _truncate_playground_scrape_payload(result)}


@app.post("/v1/playground/map")
def playground_map(request: Request, response: Response, body: PlaygroundMapBody) -> Dict[str, Any]:
    _, rem, reset, lim = check_playground_rate_limit(request)
    _playground_rate_headers(response, rem, reset, lim)
    err = validate_request_url(body.url, force_public_only=True)
    if err:
        raise HTTPException(status_code=400, detail={"code": "invalid_url", "message": err})
    out = core.map_domain(
        url=body.url,
        user_id=None,
        key_id=None,
        search=body.search,
        ignoreSubdomains=body.ignoreSubdomains,
        usage_endpoint="/v1/playground/map",
    )
    if not out.get("success"):
        raise HTTPException(status_code=400, detail={"code": "map_failed", "message": out.get("error", "Map failed")})
    links = list(out.get("links") or [])
    truncated = len(links) > _PLAYGROUND_MAP_MAX
    return {
        "success": True,
        "links": links[:_PLAYGROUND_MAP_MAX],
        "truncated": truncated,
        "total_found": len(links),
    }


@app.post("/v1/playground/crawl")
def playground_crawl(request: Request, response: Response, body: PlaygroundUrlBody) -> Dict[str, Any]:
    _, rem, reset, lim = check_playground_rate_limit(request)
    _playground_rate_headers(response, rem, reset, lim)
    err = validate_request_url(body.url, force_public_only=True)
    if err:
        raise HTTPException(status_code=400, detail={"code": "invalid_url", "message": err})
    job_id: Optional[str] = None
    last_err: Optional[str] = None
    for event in core.crawl_site_streaming(
        url=body.url,
        user_id=None,
        key_id=None,
        limit=_PLAYGROUND_CRAWL_LIMIT,
        maxDepth=0,
        ignore_subdomains=False,
        webhook_url=None,
        webhook_secret=None,
        usage_endpoint="/v1/playground/crawl",
    ):
        if event.get("type") == "job":
            job_id = event.get("id")
        if event.get("type") == "error":
            last_err = str(event.get("content", "Unknown error"))
    if last_err:
        raise HTTPException(status_code=500, detail={"code": "crawl_failed", "message": last_err})
    if not job_id:
        raise HTTPException(status_code=500, detail={"code": "crawl_failed", "message": "No job id"})
    rows = core.get_job_results(job_id)
    return {"success": True, "job_id": job_id, "data": _truncate_crawl_rows(rows)}


@app.post("/v1/auth/register")
def auth_register(req: RegisterRequest) -> Dict[str, Any]:
    if not core.registration_is_open():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "registration_closed",
                "message": "Registration is closed (set ALLOW_REGISTRATION=true to allow more accounts)",
            },
        )
    out = core.register_user(req.email, req.password, req.full_name)
    if not out.get("success"):
        raise HTTPException(status_code=400, detail=out.get("error", "Registration failed"))
    return {"success": True, "user": out["user"]}


@app.post("/v1/auth/login")
def auth_login(req: LoginRequest) -> Dict[str, Any]:
    out = core.login_user(req.email, req.password)
    if not out.get("success"):
        raise HTTPException(status_code=401, detail=out.get("error", "Login failed"))
    token = core.create_session_token(out["user"]["id"])
    return {"success": True, "user": out["user"], "session_token": token, "token_type": "Bearer", "expires_in_hours": 72}


@app.post("/v1/auth/logout")
def auth_logout(authorization: Annotated[Optional[str], Header()] = None) -> Dict[str, bool]:
    tok = None
    if authorization:
        p = authorization.split()
        if len(p) == 2 and p[0].lower() == "bearer":
            tok = p[1].strip() or None
    if tok:
        core.revoke_session_token(tok)
    return {"success": True}


@app.post("/v1/keys")
def keys_create(req: CreateKeyRequest, user_id: str = Depends(get_session_user)) -> Dict[str, Any]:
    out = core.create_api_key(user_id, req.name)
    if not out.get("success"):
        raise HTTPException(status_code=400, detail=out.get("error", "Could not create key"))
    return {
        "success": True,
        "key": {
            "id": out["key"]["id"],
            "name": out["key"]["name"],
            "value": out["key"]["value"],
            "hint": "Store this value securely; it will not be shown again.",
        },
    }


@app.get("/v1/keys")
def keys_list(user_id: str = Depends(get_session_user)) -> Dict[str, Any]:
    return {"success": True, "keys": core.list_api_keys_masked(user_id)}


@app.delete("/v1/keys/{key_id}")
def keys_delete(key_id: str, user_id: str = Depends(get_session_user)) -> Dict[str, Any]:
    out = core.delete_api_key(user_id, key_id)
    if not out.get("success"):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"success": True}


@app.get("/v1/usage/summary")
def usage_summary(
    user_id: str = Depends(get_session_user),
    days: int = Query(30, ge=1, le=365),
) -> Dict[str, Any]:
    """Dashboard aggregates for the signed-in account."""
    return core.get_usage_summary(user_id, days)


@app.get("/v1/usage/fetch-savings")
def usage_fetch_savings(
    user_id: str = Depends(get_account_user_id),
    days: int = Query(30, ge=1, le=365),
) -> Dict[str, Any]:
    """Estimated credit savings vs always using ASP/anti-bot tier."""
    from fetch_events import get_fetch_savings

    return get_fetch_savings(user_id, days)


@app.post("/v1/scrape")
def scrape(
    req: ScrapeRequest,
    response: Response,
    ctx: ApiContext = Depends(get_api_context),
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
) -> Any:
    _rate_headers(response, ctx)
    _check_target_url(req.url)
    wu, ws, gen_secret = _ensure_webhook_secret(req.webhook, req.webhook_secret)

    if req.async_mode:
        job_id = core.create_job_with_idempotency(
            ctx.user_id,
            ctx.key_id,
            idempotency_key,
            "/v1/scrape",
            job_type="scrape",
            url=req.url,
            status="queued",
            webhook_url=wu,
            webhook_secret=ws,
        )
        core.spawn_scrape_thread(
            job_id,
            req.url,
            ctx.user_id,
            ctx.key_id,
            req.formats,
            req.onlyMainContent,
            req.actions,
            req.schema_,
            render_js=req.renderJs,
            asp=req.asp,
            proxy_pool=req.proxyPool,
            country=req.country,
        )
        out: Dict[str, Any] = {
            "success": True,
            "id": job_id,
            "status": "queued",
            "url": req.url,
        }
        if gen_secret and wu:
            out["webhook_secret"] = ws
            out["webhook_secret_hint"] = "Store this secret to verify webhook signatures; it is not shown again."
        response.status_code = 202
        return out

    result: Optional[Dict[str, Any]] = None
    last_err: Optional[str] = None
    for event in core.scrape_page_streaming(
        url=req.url,
        user_id=ctx.user_id,
        key_id=ctx.key_id,
        formats=req.formats,
        onlyMainContent=req.onlyMainContent,
        actions=req.actions,
        schema=req.schema_,
        webhook_url=wu,
        webhook_secret=ws,
        render_js=req.renderJs,
        asp=req.asp,
        proxy_pool=req.proxyPool,
        country=req.country,
    ):
        et = event.get("type")
        if et == "result":
            result = event.get("data")
        elif et == "error":
            last_err = str(event.get("content", "Unknown error"))
    if last_err:
        raise HTTPException(status_code=500, detail={"code": "scrape_failed", "message": last_err})
    if not result:
        raise HTTPException(status_code=500, detail={"code": "scrape_failed", "message": "No result from scrape"})
    body: Dict[str, Any] = {"success": True, "data": result}
    if gen_secret and wu:
        body["webhook_secret"] = ws
        body["webhook_secret_hint"] = "Store this secret to verify webhook signatures; it is not shown again."
    return body


@app.post("/v1/crawl", status_code=202)
def crawl(
    req: CrawlRequest,
    response: Response,
    ctx: ApiContext = Depends(get_api_context),
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
) -> Dict[str, Any]:
    _rate_headers(response, ctx)
    _check_target_url(req.url)
    wu, ws, gen_secret = _ensure_webhook_secret(req.webhook, req.webhook_secret)
    job_id = core.create_job_with_idempotency(
        ctx.user_id,
        ctx.key_id,
        idempotency_key,
        "/v1/crawl",
        job_type="crawl",
        url=req.url,
        status="queued",
        webhook_url=wu,
        webhook_secret=ws,
    )
    core.spawn_crawl_thread(
        job_id,
        req.url,
        ctx.user_id,
        ctx.key_id,
        req.limit,
        req.maxDepth,
        req.ignoreSubdomains,
        render_js=req.renderJs,
        asp=req.asp,
        proxy_pool=req.proxyPool,
        country=req.country,
    )
    out: Dict[str, Any] = {"success": True, "id": job_id, "status": "queued", "url": req.url}
    if gen_secret and wu:
        out["webhook_secret"] = ws
        out["webhook_secret_hint"] = "Store this secret to verify webhook signatures; it is not shown again."
    return out


def _job_event_stream(job_id: str, ctx: ApiContext, stream_format: str) -> Iterator[bytes]:
    last_log_id = 0
    max_ticks = 3600
    for _ in range(max_ticks):
        job = _job_for_context(ctx, job_id)
        if not job:
            err = json.dumps({"code": "not_found", "message": "Job not found"})
            if stream_format == "ndjson":
                yield (json.dumps({"type": "error", "data": {"detail": "not_found"}}) + "\n").encode()
            else:
                yield f"event: error\ndata: {err}\n\n".encode()
            return
        for row in core.get_job_logs_after(job_id, last_log_id):
            last_log_id = max(last_log_id, int(row["id"]))
            if stream_format == "ndjson":
                yield (json.dumps({"type": "log", "data": row}) + "\n").encode()
            else:
                yield f"event: log\ndata: {json.dumps(row)}\n\n".encode()
        st = job.get("status")
        if st in ("completed", "failed"):
            payload = {
                "status": st,
                "progress": job.get("progress") or 0,
                "error_message": job.get("error_message"),
            }
            if stream_format == "ndjson":
                yield (json.dumps({"type": "job", "data": payload}) + "\n").encode()
            else:
                yield f"event: job\ndata: {json.dumps(payload)}\n\n".encode()
            return
        time.sleep(0.5)
    msg = {"message": "stream ended (max duration)"}
    if stream_format == "ndjson":
        yield (json.dumps({"type": "timeout", "data": msg}) + "\n").encode()
    else:
        yield f"event: timeout\ndata: {json.dumps(msg)}\n\n".encode()


@app.get("/v1/jobs")
def list_jobs(
    response: Response,
    ctx: ApiContext = Depends(get_api_context),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    _rate_headers(response, ctx)
    if require_auth_enabled() and not ctx.user_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "API key required"},
        )
    if not ctx.user_id:
        return {"jobs": []}
    rows = core.get_job_history(ctx.user_id, limit)
    jobs: List[Dict[str, Any]] = []
    for j in rows:
        jobs.append(
            {
                "id": j["id"],
                "type": j["type"],
                "url": j["url"],
                "status": j["status"],
                "progress": j.get("progress") or 0,
                "created_at": j.get("created_at"),
                "finished_at": j.get("finished_at"),
                "error_message": j.get("error_message"),
            }
        )
    return {"jobs": jobs}


@app.get("/v1/jobs/{job_id}")
def get_job(
    job_id: str,
    response: Response,
    ctx: ApiContext = Depends(get_api_context),
) -> Dict[str, Any]:
    _rate_headers(response, ctx)
    job = _job_for_context(ctx, job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Job not found"})
    return {
        "id": job["id"],
        "type": job["type"],
        "status": job["status"],
        "progress": job.get("progress") or 0,
        "error_message": job.get("error_message"),
        "url": job["url"],
        "created_at": job.get("created_at"),
        "finished_at": job.get("finished_at"),
        "webhook_url": job.get("webhook_url"),
    }


@app.get("/v1/jobs/{job_id}/stream")
def job_stream(
    job_id: str,
    response: Response,
    ctx: ApiContext = Depends(get_api_context),
    stream_format: str = Query("sse", alias="format"),
) -> StreamingResponse:
    _rate_headers(response, ctx)
    if stream_format not in ("sse", "ndjson"):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_format", "message": "format must be sse or ndjson"},
        )
    if not _job_for_context(ctx, job_id):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Job not found"})
    if stream_format == "ndjson":
        return StreamingResponse(
            _job_event_stream(job_id, ctx, "ndjson"),
            media_type="application/x-ndjson",
        )
    return StreamingResponse(
        _job_event_stream(job_id, ctx, "sse"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/v1/crawl/{job_id}")
def crawl_status(
    job_id: str,
    response: Response,
    ctx: ApiContext = Depends(get_api_context),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> Dict[str, Any]:
    _rate_headers(response, ctx)
    if ctx.user_id:
        job = core.get_job_for_user(job_id, ctx.user_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if core.get_job_results_for_user(job_id, ctx.user_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")
    else:
        job = core.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
    total = core.count_job_results(job_id)
    rows = core.get_job_results(job_id, offset=offset, limit=limit)
    return {
        "id": job_id,
        "status": job.get("status"),
        "data": rows,
        "pagination": {
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": offset + len(rows) < total,
        },
    }


@app.post("/v1/map")
def map_site(
    req: MapRequest,
    response: Response,
    ctx: ApiContext = Depends(get_api_context),
) -> Dict[str, Any]:
    _rate_headers(response, ctx)
    _check_target_url(req.url)
    out = core.map_domain(
        url=req.url,
        user_id=ctx.user_id,
        key_id=ctx.key_id,
        search=req.search,
        ignoreSubdomains=req.ignoreSubdomains,
    )
    if not out.get("success"):
        raise HTTPException(status_code=400, detail=out.get("error", "Map failed"))
    return out


# --- Media extractors (manifest URLs only) ---


@app.get("/v1/extract/media/supported")
def extract_media_supported() -> Dict[str, Any]:
    from media_extract import list_supported

    return list_supported()


@app.post("/v1/extract/media")
def extract_media(
    req: ExtractMediaRequest,
    response: Response,
    ctx: ApiContext = Depends(get_api_context),
) -> Dict[str, Any]:
    _rate_headers(response, ctx)
    _check_target_url(req.url)
    from media_extract import extract_media_url

    out = extract_media_url(
        req.url,
        user_id=ctx.user_id,
        key_id=ctx.key_id,
        render_js=req.renderJs,
    )
    if not out.get("success"):
        code = out.get("error") or "extract_failed"
        status = 400 if code in ("invalid_url", "unsupported_site") else 500
        raise HTTPException(
            status_code=status,
            detail={"code": code, "message": out.get("message") or code},
        )
    core.record_api_usage(ctx.user_id, ctx.key_id, "/v1/extract/media", 200, 0)
    return out


# Admin routes below — billing lives in routers/billing.py (gated by HOSTED_MODE).


# --- Admin (ADMIN_SECRET bearer token) ---


@app.get("/v1/admin/health")
def admin_health(_: None = Depends(get_admin_context)) -> Dict[str, Any]:
    return core.admin_get_health()


@app.get("/v1/admin/stats")
def admin_stats(_: None = Depends(get_admin_context)) -> Dict[str, Any]:
    return core.admin_get_stats()


@app.get("/v1/admin/users")
def admin_users(
    _: None = Depends(get_admin_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
) -> Dict[str, Any]:
    return core.admin_list_users(limit=limit, offset=offset, search=search)


@app.delete("/v1/admin/users/{user_id}")
def admin_users_delete(
    user_id: str,
    _: None = Depends(get_admin_context),
) -> Dict[str, Any]:
    if not core.admin_delete_user(user_id):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "User not found"})
    return {"success": True}


@app.get("/v1/admin/jobs")
def admin_jobs(
    _: None = Depends(get_admin_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None, alias="type"),
) -> Dict[str, Any]:
    return core.admin_list_jobs(limit=limit, offset=offset, status=status, job_type=job_type)


@app.delete("/v1/admin/jobs/{job_id}")
def admin_jobs_delete(
    job_id: str,
    _: None = Depends(get_admin_context),
) -> Dict[str, Any]:
    if not core.admin_delete_job(job_id):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Job not found"})
    return {"success": True}
