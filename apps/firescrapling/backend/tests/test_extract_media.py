"""Offline tests for media extractors (no network)."""
from __future__ import annotations

from extractors import find_extractor, supported_sites
from extractors.anime3rb import Anime3rbExtractor
from extractors.reelshort import ReelshortExtractor
from media_extract import extract_media_from_html, list_supported
from tests.fixtures.media_html import (
    ANIME3RB_CATALOG,
    ANIME3RB_EPISODE,
    ANIME3RB_SERIES,
    REELSHORT_CATALOG,
    REELSHORT_EPISODE,
    REELSHORT_SERIES,
)


def test_supported_sites_lists_both() -> None:
    sites = supported_sites()
    names = {s["name"] for s in sites}
    assert "anime3rb" in names
    assert "reelshort" in names
    out = list_supported()
    assert out["success"] is True
    assert "proxy" in out["boundary"].lower() or "rehost" in out["boundary"].lower()


def test_find_extractor_by_domain() -> None:
    assert isinstance(find_extractor("https://anime3rb.com/titles/list"), Anime3rbExtractor)
    assert isinstance(find_extractor("https://www.reelshort.com/movie/x"), ReelshortExtractor)
    assert find_extractor("https://example.com/") is None


def test_anime3rb_catalog() -> None:
    r = extract_media_from_html("https://anime3rb.com/titles/list", ANIME3RB_CATALOG)
    assert r["success"] is True
    assert r["kind"] == "catalog"
    assert r["extractor"] == "anime3rb"
    titles = {i["title"] for i in r["data"]["items"]}
    assert "One Piece" in titles
    assert "Naruto" in titles
    for item in r["data"]["items"]:
        assert item["page_url"].startswith("http")
        # URLs only — no binary payloads
        assert "content" not in item


def test_anime3rb_series_episodes() -> None:
    r = extract_media_from_html("https://anime3rb.com/titles/one-piece", ANIME3RB_SERIES)
    assert r["kind"] == "series"
    assert r["data"]["title"] == "One Piece"
    assert r["data"]["poster"] == "https://cdn.example.com/op-poster.jpg"
    assert len(r["data"]["episodes"]) == 2
    assert r["data"]["episodes"][0]["page_url"].endswith("/episode/1")


def test_anime3rb_episode_m3u8() -> None:
    r = extract_media_from_html(
        "https://anime3rb.com/titles/one-piece/episode/1",
        ANIME3RB_EPISODE,
    )
    assert r["kind"] == "episode"
    assert r["data"]["stream"] is not None
    assert r["data"]["stream"]["type"] == "hls"
    assert r["data"]["stream"]["url"].endswith(".m3u8")


def test_reelshort_catalog() -> None:
    r = extract_media_from_html("https://www.reelshort.com/", REELSHORT_CATALOG)
    assert r["kind"] == "catalog"
    assert r["extractor"] == "reelshort"
    assert len(r["data"]["items"]) >= 2


def test_reelshort_series() -> None:
    r = extract_media_from_html("https://www.reelshort.com/movie/secret-love", REELSHORT_SERIES)
    assert r["kind"] == "series"
    assert "Secret Love" in r["data"]["title"]
    assert len(r["data"]["episodes"]) == 2


def test_reelshort_episode_hls() -> None:
    r = extract_media_from_html(
        "https://www.reelshort.com/movie/secret-love/episode/1",
        REELSHORT_EPISODE,
    )
    assert r["kind"] == "episode"
    assert r["data"]["stream"]["type"] == "hls"
    assert ".m3u8" in r["data"]["stream"]["url"]


def test_unsupported_site() -> None:
    r = extract_media_from_html("https://example.com/watch", "<html></html>")
    assert r["success"] is False
    assert r["error"] == "unsupported_site"
