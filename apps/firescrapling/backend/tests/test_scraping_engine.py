"""Unit tests for scraping_engine helpers (no network — fixture server or pure HTML)."""
from __future__ import annotations

import time

import pytest

import scraping_engine
from scraping_engine import (
    crawl_bfs_iter,
    extract_links_from_html,
    extract_title_from_html,
    html_to_markdown,
    normalize_http_url,
    read_response_cache,
    same_site,
    write_response_cache,
)
from tests.fixtures_html import HTML_INDEX, HTML_PAGE2


# ---------------------------------------------------------------------------
# normalize_http_url
# ---------------------------------------------------------------------------

def test_normalize_strips_fragment() -> None:
    assert "#" not in normalize_http_url("http://example.com/path#frag")


def test_normalize_lowercases_host() -> None:
    result = normalize_http_url("http://EXAMPLE.COM/Path")
    assert result.startswith("http://example.com")


def test_normalize_preserves_path_case() -> None:
    result = normalize_http_url("http://example.com/Path/File")
    assert "/Path/File" in result


# ---------------------------------------------------------------------------
# same_site
# ---------------------------------------------------------------------------

def test_same_site_identical_host() -> None:
    assert same_site("https://foo.com/", "https://foo.com/bar", ignore_subdomains=False)


def test_same_site_cross_scheme_still_matches() -> None:
    # http vs https are both on the same registrable domain
    assert same_site("http://foo.com/", "https://foo.com/page", ignore_subdomains=False)


def test_same_site_subdomains_share_registrable_domain() -> None:
    assert same_site(
        "https://a.foo.com/",
        "https://b.foo.com/page",
        ignore_subdomains=False,
    )


def test_same_site_ignore_subdomains_rejects_cross_subdomain() -> None:
    assert not same_site(
        "https://a.foo.com/",
        "https://b.foo.com/page",
        ignore_subdomains=True,
    )


def test_same_site_rejects_different_domain() -> None:
    assert not same_site("https://foo.com/", "https://bar.com/", ignore_subdomains=False)


# ---------------------------------------------------------------------------
# HTML extraction helpers
# ---------------------------------------------------------------------------

def test_extract_title() -> None:
    assert "Fixture" in extract_title_from_html(HTML_INDEX)


def test_extract_title_missing() -> None:
    # No <title> tag — should not raise; returns something reasonable.
    result = extract_title_from_html("<html><body>No title</body></html>")
    assert isinstance(result, str)


def test_html_to_markdown_main_content_includes_heading() -> None:
    md = html_to_markdown(HTML_INDEX, "http://127.0.0.1/", only_main_content=True)
    assert "Welcome" in md


def test_html_to_markdown_full_page_includes_heading() -> None:
    md = html_to_markdown(HTML_INDEX, "http://127.0.0.1/", only_main_content=False)
    assert "Welcome" in md


def test_html_to_markdown_main_content_body() -> None:
    md = html_to_markdown(HTML_INDEX, "http://127.0.0.1/", only_main_content=True)
    assert "Primary article body" in md


def test_extract_links_finds_anchor() -> None:
    links = extract_links_from_html(HTML_INDEX, "http://127.0.0.1:9/")
    assert any("/page2" in link for link in links)


def test_extract_links_absolute_url() -> None:
    html = '<html><body><a href="https://other.example.com/page">link</a></body></html>'
    links = extract_links_from_html(html, "http://example.com/")
    assert any("other.example.com" in link for link in links)


# ---------------------------------------------------------------------------
# crawl_bfs_iter — via local fixture server
# ---------------------------------------------------------------------------

def test_crawl_finds_multiple_pages(fixture_server: str) -> None:
    pages = []
    for ev, payload in crawl_bfs_iter(fixture_server + "/", limit=10, max_depth=2, ignore_subdomains=False):
        if ev == "page":
            pages.append(payload)
    assert len(pages) >= 2, f"Expected >=2 pages, got {len(pages)}"


def test_crawl_deduplicates_urls(fixture_server: str) -> None:
    seen_urls: list[str] = []
    for ev, payload in crawl_bfs_iter(fixture_server + "/", limit=10, max_depth=2, ignore_subdomains=False):
        if ev == "page":
            seen_urls.append(payload["url"])
    assert len(seen_urls) == len(set(seen_urls)), "crawl yielded duplicate URLs"


def test_crawl_respects_depth_limit(fixture_server: str) -> None:
    pages = []
    for ev, payload in crawl_bfs_iter(fixture_server + "/", limit=10, max_depth=0, ignore_subdomains=False):
        if ev == "page":
            pages.append(payload)
    # depth=0 → only the seed page
    assert len(pages) == 1, f"depth=0 should yield only 1 page, got {len(pages)}"


def test_crawl_page2_discovered(fixture_server: str) -> None:
    urls = set()
    for ev, payload in crawl_bfs_iter(fixture_server + "/", limit=10, max_depth=2, ignore_subdomains=False):
        if ev == "page":
            urls.add(payload["url"])
    assert any("/page2" in u for u in urls), f"/page2 not found in {urls}"


def test_crawl_done_event_has_count(fixture_server: str) -> None:
    for ev, payload in crawl_bfs_iter(fixture_server + "/", limit=10, max_depth=2, ignore_subdomains=False):
        if ev == "done":
            assert payload["count"] >= 2
            break
    else:
        pytest.fail("crawl_bfs_iter never emitted a 'done' event")


# ---------------------------------------------------------------------------
# Response cache — TTL
# ---------------------------------------------------------------------------

def test_cache_write_and_read(tmp_path: "pytest.TempPathFactory", monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scraping_engine, "_CACHE_ROOT", str(tmp_path / "cache"))
    write_response_cache("http://example.com/", False, "markdown", {"html": "<p>hi</p>"})
    cached = read_response_cache("http://example.com/", False, "markdown")
    assert cached is not None
    assert cached.get("html") == "<p>hi</p>"


def test_cache_expired_returns_none(tmp_path: "pytest.TempPathFactory", monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scraping_engine, "_CACHE_ROOT", str(tmp_path / "cache"))
    write_response_cache("http://example.com/expired", False, "markdown", {"html": "<p>old</p>"})
    # Set TTL to 0 so every entry is immediately stale.
    monkeypatch.setattr(scraping_engine, "CACHE_TTL_SECONDS", 0)
    time.sleep(0.01)
    cached = read_response_cache("http://example.com/expired", False, "markdown")
    assert cached is None


def test_cache_miss_returns_none(tmp_path: "pytest.TempPathFactory", monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scraping_engine, "_CACHE_ROOT", str(tmp_path / "cache"))
    result = read_response_cache("http://example.com/notcached", False, "markdown")
    assert result is None
