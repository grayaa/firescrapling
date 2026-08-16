"""HTTP client for the FireScrapling REST API (API-key auth)."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"


class FireScraplingClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = (api_key or os.environ.get("FIRESCRAPLING_API_KEY") or "").strip()
        self.base_url = (base_url or os.environ.get("FIRESCRAPLING_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError(
                "FIRESCRAPLING_API_KEY is required (fs_… key from the dashboard)"
            )

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _raise_for_api_error(self, r: httpx.Response) -> None:
        if r.is_success:
            return
        try:
            body = r.json()
            err = body.get("error") or {}
            msg = err.get("message") or body
        except Exception:
            msg = r.text
        raise RuntimeError(f"API {r.status_code}: {msg}")

    def scrape(
        self,
        url: str,
        *,
        formats: Optional[list[str]] = None,
        only_main_content: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "url": url,
            "formats": formats or ["markdown"],
            "onlyMainContent": only_main_content,
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/v1/scrape", json=payload, headers=self._headers())
            self._raise_for_api_error(r)
            return r.json()

    def crawl(
        self,
        url: str,
        *,
        limit: int = 20,
        max_depth: int = 2,
        ignore_subdomains: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "url": url,
            "limit": limit,
            "maxDepth": max_depth,
            "ignoreSubdomains": ignore_subdomains,
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/v1/crawl", json=payload, headers=self._headers())
            self._raise_for_api_error(r)
            return r.json()

    def crawl_status(
        self,
        job_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        params = {"offset": offset, "limit": limit}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(
                f"{self.base_url}/v1/crawl/{job_id}",
                params=params,
                headers=self._headers(),
            )
            self._raise_for_api_error(r)
            return r.json()

    def map_site(
        self,
        url: str,
        *,
        search: Optional[str] = None,
        ignore_subdomains: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "url": url,
            "ignoreSubdomains": ignore_subdomains,
        }
        if search:
            payload["search"] = search
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/v1/map", json=payload, headers=self._headers())
            self._raise_for_api_error(r)
            return r.json()

    def extract_media(self, url: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(
                f"{self.base_url}/v1/extract/media",
                json={"url": url},
                headers=self._headers(),
            )
            self._raise_for_api_error(r)
            return r.json()

    def fetch_savings(self, days: int = 30) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(
                f"{self.base_url}/v1/usage/fetch-savings",
                params={"days": days},
                headers=self._headers(),
            )
            self._raise_for_api_error(r)
            return r.json()
