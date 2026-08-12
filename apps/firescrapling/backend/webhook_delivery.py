"""HTTPS webhook delivery with HMAC-SHA256 signing and retries."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4
BASE_DELAY = 0.5


def sign_body(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def deliver_webhook(
    url: str,
    secret: str,
    event: str,
    payload: Dict[str, Any],
    idempotency_key: str,
) -> bool:
    """
    POST JSON to url with signature headers. Retries on failure with exponential backoff.
    Returns True if a 2xx response was received.
    """
    body_obj = {
        "event": event,
        "idempotency_key": idempotency_key,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **payload,
    }
    body = json.dumps(body_obj, separators=(",", ":")).encode("utf-8")
    sig = sign_body(secret, body)
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
        "X-FireScrapling-Event": event,
        "X-FireScrapling-Signature": sig,
        "X-Idempotency-Key": idempotency_key,
        "User-Agent": "FireScrapling-Webhook/1.0",
    }
    ctx = ssl.create_default_context()

    for attempt in range(MAX_ATTEMPTS):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                code = resp.getcode()
                if 200 <= code < 300:
                    return True
                logger.warning("webhook non-2xx: %s %s", code, url)
        except urllib.error.HTTPError as e:
            logger.warning("webhook HTTPError %s: %s", e.code, url)
        except Exception as e:
            logger.warning("webhook attempt %s failed: %s", attempt + 1, e)
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(BASE_DELAY * (2**attempt))
    return False
