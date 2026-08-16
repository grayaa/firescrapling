"""Tests for fetch_provider selection and Scrapfly / Scrape.do adapters (mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fetch_provider import (
    FetchResult,
    LocalFetcher,
    ScrapedoFetcher,
    ScrapflyFetcher,
    default_fetch_options,
    get_fetcher,
)
from settings import clear_settings_cache


@pytest.fixture(autouse=True)
def _clear_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SCRAPE_API_KEY", raising=False)
    monkeypatch.delenv("SCRAPE_DO_API_KEY", raising=False)
    monkeypatch.delenv("SCRAPFLY_API_KEY", raising=False)
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_local_provider_when_no_paid_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FETCH_PROVIDER", "auto")
    clear_settings_cache()
    assert isinstance(get_fetcher(), LocalFetcher)
    opts = default_fetch_options()
    assert opts["render_js"] is False
    assert opts["asp"] is False


def test_auto_prefers_scrapedo_over_scrapfly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FETCH_PROVIDER", "auto")
    monkeypatch.setenv("SCRAPE_API_KEY", "sd-key")
    monkeypatch.setenv("SCRAPFLY_API_KEY", "sf-key")
    clear_settings_cache()
    assert isinstance(get_fetcher(), ScrapedoFetcher)


def test_scrapfly_provider_when_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FETCH_PROVIDER", "scrapfly")
    monkeypatch.setenv("SCRAPFLY_API_KEY", "sf-test-key")
    monkeypatch.setenv("SCRAPFLY_DEFAULT_RENDER_JS", "false")
    monkeypatch.setenv("SCRAPFLY_DEFAULT_ASP", "false")
    clear_settings_cache()
    assert isinstance(get_fetcher(), ScrapflyFetcher)
    opts = default_fetch_options()
    assert opts["render_js"] is False
    assert opts["asp"] is False


def test_scrapfly_fetch_with_mocked_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAPFLY_API_KEY", "k")
    clear_settings_cache()

    mock_api = MagicMock()
    mock_api.scrape_result = {
        "content": "<p>ok</p>",
        "status_code": 200,
        "url": "https://example.com/",
    }
    mock_client_inst = MagicMock()
    mock_client_inst.scrape.return_value = mock_api

    fake_mod = MagicMock()
    fake_mod.ScrapflyClient = MagicMock(return_value=mock_client_inst)
    fake_mod.ScrapeConfig = MagicMock(side_effect=lambda **kwargs: kwargs)
    fake_mod.ScrapeApiResponse = object

    import sys

    sys.modules["scrapfly"] = fake_mod
    try:
        result = ScrapflyFetcher("k").fetch("https://example.com/", render_js=True, asp=True)
        assert result.html_content == "<p>ok</p>"
        assert result.status == 200
        assert "example.com" in result.url
        mock_client_inst.scrape.assert_called_once()
        cfg = fake_mod.ScrapeConfig.call_args.kwargs
        assert cfg["render_js"] is True
        assert cfg["asp"] is True
    finally:
        sys.modules.pop("scrapfly", None)


def test_scrapedo_fetch_maps_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><body>" + ("hello world " * 20) + "</body></html>"

    with patch("requests.get", return_value=mock_resp) as get:
        result = ScrapedoFetcher("tok").fetch(
            "https://example.com/",
            render_js=True,
            asp=True,
            country="us",
        )
    assert result.status == 200
    assert "hello world" in result.html_content
    params = get.call_args.kwargs["params"]
    assert params["token"] == "tok"
    assert params["render"] == "true"
    assert params["super"] == "true"
    assert params["geoCode"] == "us"


def test_capabilities_endpoint(client) -> None:
    r = client.get("/v1/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["markdown"] is True
    assert body["webhooks"] is True
    assert "scrapfly" in body
    assert "scrapedo" in body
    assert "queue" in body
    assert body["fetch_provider"] == "local"
