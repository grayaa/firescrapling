"""FastAPI dependencies: API keys, sessions, rate limits."""
from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Request

import main as core

# --- Rate limiting (in-process; use Redis for multi-node) ---

_WINDOW_SEC = 60
_DEFAULT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))


class _SlidingWindow:
    def __init__(self) -> None:
        self._lock = Lock()
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, limit: int) -> tuple[bool, int, int]:
        """Returns (allowed, remaining, reset_epoch_sec)."""
        now = time.time()
        cutoff = now - _WINDOW_SEC
        with self._lock:
            arr = self._hits[key]
            arr[:] = [t for t in arr if t > cutoff]
            if len(arr) >= limit:
                reset = int(arr[0] + _WINDOW_SEC) if arr else int(now + _WINDOW_SEC)
                return False, 0, reset
            arr.append(now)
            remaining = max(0, limit - len(arr))
            reset = int(now + _WINDOW_SEC)
            return True, remaining, reset


_rate_limiter = _SlidingWindow()


def playground_enabled() -> bool:
    return os.environ.get("PLAYGROUND_ENABLED", "true").strip().lower() not in ("0", "false", "no")


def playground_rate_limit_per_minute() -> int:
    return max(1, int(os.environ.get("PLAYGROUND_RATE_LIMIT_PER_MINUTE", "8")))


def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()[:200]
    if request.client and request.client.host:
        return str(request.client.host)[:200]
    return "unknown"


def check_playground_rate_limit(request: Request) -> tuple[str, int, int, int]:
    """
    Enforce public playground IP rate limit. Returns (client_ip, remaining, reset_epoch, limit).
    Raises HTTPException 404 if disabled, 429 if exceeded.
    """
    if not playground_enabled():
        raise HTTPException(
            status_code=404,
            detail={"code": "playground_disabled", "message": "Public playground is disabled"},
        )
    ip = get_client_ip(request)
    lim = playground_rate_limit_per_minute()
    ok, rem, reset = _rate_limiter.allow(f"play:{ip}", lim)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={"code": "playground_rate_limited", "message": "Too many playground requests. Try again later."},
            headers={
                "Retry-After": str(max(1, reset - int(time.time()))),
                "X-RateLimit-Limit": str(lim),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset),
            },
        )
    return ip, rem, reset, lim


def _rate_limit_key(user_id: Optional[str], key_id: Optional[str]) -> str:
    if key_id:
        return f"k:{key_id}"
    if user_id:
        return f"u:{user_id}"
    return "anon"


@dataclass
class ApiContext:
    user_id: Optional[str]
    key_id: Optional[str]
    rate_limit_remaining: int
    rate_limit_reset: int


def require_auth_enabled() -> bool:
    return os.environ.get("API_REQUIRE_AUTH", "true").strip().lower() not in ("0", "false", "no")


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


async def get_api_context(
    request: Request,
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
) -> ApiContext:
    token = _extract_bearer_token(authorization) or (x_api_key.strip() if x_api_key else None)

    if not token:
        if not require_auth_enabled():
            lim = _DEFAULT_PER_MIN
            ok, rem, reset = _rate_limiter.allow("anon", lim)
            if not ok:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(max(1, reset - int(time.time()))), "X-RateLimit-Limit": str(lim), "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)},
                )
            return ApiContext(user_id=None, key_id=None, rate_limit_remaining=rem, rate_limit_reset=reset)
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Use Authorization: Bearer <key> or X-API-Key header.",
        )

    resolved = core.resolve_api_key(token)
    if not resolved:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    user_id = resolved["user_id"]
    key_id = resolved["key_id"]
    core.touch_api_key_last_used(key_id)

    lim = _DEFAULT_PER_MIN
    ok, rem, reset = _rate_limiter.allow(_rate_limit_key(user_id, key_id), lim)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, reset - int(time.time()))), "X-RateLimit-Limit": str(lim), "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)},
        )

    request.state.api_user_id = user_id
    request.state.api_key_id = key_id
    return ApiContext(user_id=user_id, key_id=key_id, rate_limit_remaining=rem, rate_limit_reset=reset)


async def get_session_user(
    authorization: Annotated[Optional[str], Header()] = None,
) -> str:
    """Bearer session token (not API key) for /v1/keys management."""
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing session token")
    user_id = core.resolve_session_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user_id
