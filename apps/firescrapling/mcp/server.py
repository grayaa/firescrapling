"""FireScrapling MCP server (stdio) — tools over the REST API.

Env:
  FIRESCRAPLING_API_KEY  fs_… key (required)
  FIRESCRAPLING_BASE_URL  default http://localhost:8000

Run:
  python -m server
  # or: python server.py
"""
from __future__ import annotations

import json
import sys
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from client import FireScraplingClient

mcp = FastMCP("firescrapling")


def _client() -> FireScraplingClient:
    return FireScraplingClient()


def _md_result(data: Any) -> str:
    """Prefer markdown field; otherwise JSON for agents."""
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict) and isinstance(inner.get("markdown"), str):
            return inner["markdown"]
        if isinstance(inner, list):
            parts = []
            for row in inner:
                if isinstance(row, dict):
                    title = row.get("title") or ""
                    url = row.get("url") or ""
                    md = row.get("markdown") or ""
                    parts.append(f"## {title}\n\nURL: {url}\n\n{md}")
            if parts:
                return "\n\n---\n\n".join(parts)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def scrape(url: str, formats: Optional[str] = "markdown", only_main_content: bool = True) -> str:
    """Scrape a URL into LLM-ready markdown (or other formats).

    Args:
        url: Target page URL
        formats: Comma-separated formats (default: markdown)
        only_main_content: Prefer main content extraction
    """
    fmt_list = [f.strip() for f in (formats or "markdown").split(",") if f.strip()]
    out = _client().scrape(url, formats=fmt_list or ["markdown"], only_main_content=only_main_content)
    return _md_result(out)


@mcp.tool()
def crawl(
    url: str,
    limit: int = 20,
    max_depth: int = 2,
    ignore_subdomains: bool = False,
) -> str:
    """Start a BFS crawl job. Returns job id; poll with crawl_status.

    Args:
        url: Seed URL
        limit: Max pages
        max_depth: Max link depth from seed
        ignore_subdomains: Stay on exact host when true
    """
    out = _client().crawl(
        url,
        limit=limit,
        max_depth=max_depth,
        ignore_subdomains=ignore_subdomains,
    )
    return json.dumps(out, indent=2)


@mcp.tool()
def crawl_status(job_id: str, offset: int = 0, limit: int = 50) -> str:
    """Get crawl job status and paginated page results.

    Args:
        job_id: Crawl job id from crawl()
        offset: Result offset
        limit: Max results in this page
    """
    out = _client().crawl_status(job_id, offset=offset, limit=limit)
    return _md_result(out)


@mcp.tool()
def map(url: str, search: Optional[str] = None, ignore_subdomains: bool = False) -> str:
    """Discover links on a site (map).

    Args:
        url: Seed URL
        search: Optional substring filter for links
        ignore_subdomains: Stay on exact host when true
    """
    out = _client().map_site(url, search=search, ignore_subdomains=ignore_subdomains)
    return json.dumps(out, indent=2, ensure_ascii=False)


@mcp.tool()
def extract_media(url: str) -> str:
    """Extract media/catalog manifests (URLs only — no proxy/download) for supported sites.

    Args:
        url: Page URL on a supported media site
    """
    out = _client().extract_media(url)
    return json.dumps(out, indent=2, ensure_ascii=False)


@mcp.tool()
def fetch_savings(days: int = 30) -> str:
    """Estimated fetch-credit savings vs always using the expensive tier.

    Args:
        days: Lookback window (1–365)
    """
    out = _client().fetch_savings(days=max(1, min(365, days)))
    return json.dumps(out, indent=2, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
