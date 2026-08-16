"""Offline media extraction service — fetch HTML then run domain extractors."""
from __future__ import annotations

from typing import Any, Dict, Optional

from extractors import find_extractor, supported_sites
from security_url import validate_request_url


def list_supported() -> Dict[str, Any]:
    return {
        "success": True,
        "sites": supported_sites(),
        "boundary": (
            "Extractors return stream/poster/page URLs only. "
            "FireScrapling does not proxy, download, or rehost media."
        ),
    }


def extract_media_from_html(url: str, html: str) -> Dict[str, Any]:
    """Parse already-fetched HTML (tests / offline)."""
    ex = find_extractor(url)
    if not ex:
        return {
            "success": False,
            "error": "unsupported_site",
            "message": "No extractor matches this URL. See GET /v1/extract/media/supported.",
            "url": url,
        }
    result = ex.extract(html, url)
    result["fetch_tier"] = None
    return result


def extract_media_url(
    url: str,
    *,
    user_id: Optional[str] = None,
    key_id: Optional[str] = None,
    render_js: Optional[bool] = None,
) -> Dict[str, Any]:
    """Validate URL, fetch HTML, run matching extractor. Manifest URLs only."""
    err = validate_request_url(url)
    if err:
        return {"success": False, "error": "invalid_url", "message": err}

    ex = find_extractor(url)
    if not ex:
        return {
            "success": False,
            "error": "unsupported_site",
            "message": "No extractor matches this URL. See GET /v1/extract/media/supported.",
            "url": url,
        }

    from provider_credentials import build_fetch_context
    from scraping_engine import fetch_with_retries

    # Prefer JS when extractor declares network capture needs (player pages).
    use_js = render_js if render_js is not None else bool(getattr(ex, "needs_network_capture", False))
    fetch_ctx = build_fetch_context(user_id)
    response = fetch_with_retries(url, timeout=40, render_js=use_js, ctx=fetch_ctx)
    html = response.html_content or ""
    result = ex.extract(html, url)
    result["fetch_tier"] = getattr(response, "fetch_tier", None) or (
        "sf_js" if use_js else "local"
    )
    result["url"] = url
    return result
