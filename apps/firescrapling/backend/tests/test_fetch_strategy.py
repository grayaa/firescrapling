"""Tests for credit-aware fetch classification and escalation ladder."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fetch_provider import FetchResult
from fetch_strategy import (
    classify_fetch,
    clear_all_profiles,
    fetch_with_strategy,
    get_domain_profile,
    set_domain_profile,
    tier_specs,
)
from settings import clear_settings_cache


@pytest.fixture(autouse=True)
def _reset():
    clear_settings_cache()
    clear_all_profiles()
    yield
    clear_all_profiles()
    clear_settings_cache()


def test_classify_cloudflare_bot_wall() -> None:
    html = "<html><title>Just a moment...</title><body>cloudflare cf-browser-verification</body></html>"
    assert classify_fetch(html, 403) == "bot_wall"
    assert classify_fetch(html, 200) == "bot_wall"


def test_classify_needs_js_spa_shell() -> None:
    html = """
    <html><body><div id="__next"></div>
    <script>window.__NEXT_DATA__={}</script>
    <noscript>You need to enable JavaScript</noscript>
    </body></html>
    """
    assert classify_fetch(html, 200) == "needs_js"


def test_classify_ok_article() -> None:
    body = " ".join(["Paragraph about interesting content."] * 20)
    html = f"<html><head><title>Doc</title></head><body><article><p>{body}</p></article></body></html>"
    assert classify_fetch(html, 200) == "ok"


def test_classify_terminal_404() -> None:
    assert classify_fetch("<html>missing</html>", 404) == "terminal"


def test_classify_soft_fail_connection() -> None:
    assert classify_fetch("", None, ConnectionError("Failed to connect")) == "soft_fail"


def test_ladder_escalates_local_to_js(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FETCH_ESCALATE", "true")
    monkeypatch.setenv("SCRAPFLY_API_KEY", "k")
    monkeypatch.setenv("FETCH_PROVIDER", "scrapfly")
    monkeypatch.delenv("SCRAPE_API_KEY", raising=False)
    clear_settings_cache()

    thin = FetchResult(
        html_content='<div id="__next"></div><script>__NEXT_DATA__={}</script>',
        url="https://spa.example.com/",
        status=200,
    )
    rich = FetchResult(
        html_content="<html><body>" + ("Real article text. " * 30) + "</body></html>",
        url="https://spa.example.com/",
        status=200,
    )

    local = MagicMock()
    local.fetch.return_value = thin
    sf = MagicMock()
    sf.fetch.return_value = rich

    with patch("fetch_strategy.LocalFetcher", return_value=local), patch(
        "fetch_strategy.ScrapflyFetcher", return_value=sf
    ):
        out = fetch_with_strategy("https://spa.example.com/page")

    assert out.status == 200
    assert "Real article" in out.html_content
    assert out.fetch_tier == "sf_js"
    assert "local" in out.attempts
    assert "sf_js" in out.attempts
    assert "sf_static" not in out.attempts
    local.fetch.assert_called_once()
    sf.fetch.assert_called_once()
    assert sf.fetch.call_args.kwargs.get("render_js") is True
    assert sf.fetch.call_args.kwargs.get("asp") is False


def test_ladder_uses_scrapedo_when_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FETCH_ESCALATE", "true")
    monkeypatch.setenv("SCRAPE_API_KEY", "sd")
    monkeypatch.setenv("FETCH_PROVIDER", "auto")
    monkeypatch.delenv("SCRAPFLY_API_KEY", raising=False)
    clear_settings_cache()

    thin = FetchResult(
        html_content='<div id="__next"></div><script>__NEXT_DATA__={}</script>',
        url="https://spa2.example.com/",
        status=200,
    )
    rich = FetchResult(
        html_content="<html><body>" + ("Scrape do content here. " * 25) + "</body></html>",
        url="https://spa2.example.com/",
        status=200,
    )
    local = MagicMock()
    local.fetch.return_value = thin
    sd = MagicMock()
    sd.fetch.return_value = rich

    with patch("fetch_strategy.LocalFetcher", return_value=local), patch(
        "fetch_strategy.ScrapedoFetcher", return_value=sd
    ):
        out = fetch_with_strategy("https://spa2.example.com/page")

    assert out.fetch_tier == "sf_js"
    sd.fetch.assert_called_once()
    assert sd.fetch.call_args.kwargs.get("render_js") is True


def test_ladder_uses_cached_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FETCH_ESCALATE", "true")
    monkeypatch.setenv("SCRAPFLY_API_KEY", "k")
    monkeypatch.setenv("FETCH_PROVIDER", "scrapfly")
    monkeypatch.delenv("SCRAPE_API_KEY", raising=False)
    clear_settings_cache()

    spec = tier_specs()["sf_asp"]
    set_domain_profile("hard.example.com", "sf_asp", spec)
    assert get_domain_profile("hard.example.com")["tier"] == "sf_asp"

    rich = FetchResult(
        html_content="<html><body>" + ("Cached tier content works. " * 20) + "</body></html>",
        url="https://hard.example.com/",
        status=200,
    )
    local = MagicMock()
    sf = MagicMock()
    sf.fetch.return_value = rich

    with patch("fetch_strategy.LocalFetcher", return_value=local), patch(
        "fetch_strategy.ScrapflyFetcher", return_value=sf
    ):
        out = fetch_with_strategy("https://hard.example.com/x")

    assert out.fetch_tier == "sf_asp"
    local.fetch.assert_not_called()
    sf.fetch.assert_called_once()
    assert sf.fetch.call_args.kwargs.get("asp") is True


def test_explicit_asp_skips_ladder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FETCH_ESCALATE", "true")
    monkeypatch.setenv("SCRAPFLY_API_KEY", "k")
    monkeypatch.setenv("FETCH_PROVIDER", "scrapfly")
    monkeypatch.delenv("SCRAPE_API_KEY", raising=False)
    clear_settings_cache()

    rich = FetchResult(html_content="<p>" + ("x" * 200) + "</p>", url="https://ex.com/", status=200)
    fetcher = MagicMock()
    fetcher.fetch.return_value = rich

    with patch("fetch_provider.get_fetcher", return_value=fetcher):
        out = fetch_with_strategy("https://ex.com/", asp=True)

    assert out.fetch_tier == "explicit"
    assert out.escalated is False
    fetcher.fetch.assert_called_once()
    assert fetcher.fetch.call_args.kwargs.get("asp") is True


def test_escalate_disabled_single_shot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FETCH_ESCALATE", "false")
    monkeypatch.setenv("FETCH_PROVIDER", "local")
    monkeypatch.delenv("SCRAPFLY_API_KEY", raising=False)
    clear_settings_cache()

    rich = FetchResult(
        html_content="<html><body>" + ("Plain page content here. " * 20) + "</body></html>",
        url="https://ex.com/",
        status=200,
    )
    fetcher = MagicMock()
    fetcher.fetch.return_value = rich

    with patch("fetch_provider.get_fetcher", return_value=fetcher):
        out = fetch_with_strategy("https://ex.com/")

    assert out.fetch_tier == "default"
    fetcher.fetch.assert_called_once()


# --- Plan 07 Step 1: unhandled 4xx is terminal ---


@pytest.mark.parametrize("status", [400, 402, 405, 422])
def test_classify_unhandled_4xx_terminal(status: int) -> None:
    assert classify_fetch("", status) == "terminal"


def test_classify_400_large_body_still_terminal() -> None:
    body = " ".join(["Large body text that looks ok."] * 40)
    html = f"<html><body><p>{body}</p></body></html>"
    assert classify_fetch(html, 400) == "terminal"


def test_classify_bot_wall_and_terminal_unchanged() -> None:
    assert classify_fetch("", 401) == "bot_wall"
    assert classify_fetch("", 403) == "bot_wall"
    assert classify_fetch("", 429) == "bot_wall"
    assert classify_fetch("", 404) == "terminal"
    assert classify_fetch("", 410) == "terminal"
    assert classify_fetch("", 451) == "terminal"


def test_ladder_stops_on_400_without_asp(monkeypatch: pytest.MonkeyPatch) -> None:
    from cost_model import estimate_attempt_cost

    monkeypatch.setenv("FETCH_ESCALATE", "true")
    monkeypatch.setenv("SCRAPE_API_KEY", "stub")
    monkeypatch.setenv("FETCH_PROVIDER", "scrapedo")
    clear_settings_cache()

    thin = FetchResult(
        html_content='<div id="__next"></div><script>__NEXT_DATA__={}</script>',
        url="https://bad.example.com/",
        status=200,
    )
    bad400 = FetchResult(html_content="<html>bad request</html>", url="https://bad.example.com/", status=400)

    local = MagicMock()
    local.fetch.return_value = thin
    paid = MagicMock()
    paid.fetch.return_value = bad400

    with patch("fetch_strategy.LocalFetcher", return_value=local), patch(
        "fetch_strategy.ScrapedoFetcher", return_value=paid
    ):
        out = fetch_with_strategy("https://bad.example.com/x")

    assert out.status == 400
    assert out.attempts == ["local", "sf_js"]
    assert "sf_asp" not in out.attempts
    assert "sf_residential" not in out.attempts
    cost = estimate_attempt_cost(out.attempts, out.fetch_tier)
    assert cost <= 25


# --- Plan 07 Step 2: private hosts never reach paid ---


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/x",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
    ],
)
def test_private_host_local_only(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from fetch_context import FetchContext

    monkeypatch.setenv("FETCH_ESCALATE", "true")
    clear_settings_cache()

    ctx = FetchContext(
        provider="scrapedo",
        api_key="must-not-use",
        proxy_pool=None,
        residential_pool=None,
        country=None,
        source="byok",
        credential_id="cid",
    )
    local = MagicMock()
    local.fetch.return_value = FetchResult(
        html_content="<html><body>" + ("local ok " * 30) + "</body></html>",
        url=url,
        status=200,
    )

    def boom(*_a, **_k):
        raise AssertionError("paid fetcher must not be constructed for private hosts")

    with patch("fetch_strategy.LocalFetcher", return_value=local), patch(
        "fetch_strategy.ScrapedoFetcher", side_effect=boom
    ), patch("fetch_strategy.ScrapflyFetcher", side_effect=boom):
        out = fetch_with_strategy(url, ctx=ctx)

    assert out.attempts == ["local"]
    local.fetch.assert_called_once()


def test_public_url_still_escalates_with_ctx(monkeypatch: pytest.MonkeyPatch) -> None:
    from fetch_context import FetchContext

    monkeypatch.setenv("FETCH_ESCALATE", "true")
    clear_settings_cache()

    ctx = FetchContext(
        provider="scrapedo",
        api_key="ok-key",
        proxy_pool=None,
        residential_pool=None,
        country=None,
        source="byok",
        credential_id="cid",
    )
    thin = FetchResult(
        html_content='<div id="__next"></div><script>__NEXT_DATA__={}</script>',
        url="https://public.example.com/",
        status=200,
    )
    rich = FetchResult(
        html_content="<html><body>" + ("Public escalate ok. " * 30) + "</body></html>",
        url="https://public.example.com/",
        status=200,
    )
    local = MagicMock()
    local.fetch.return_value = thin
    paid = MagicMock()
    paid.fetch.return_value = rich

    with patch("fetch_strategy.LocalFetcher", return_value=local), patch(
        "fetch_strategy.ScrapedoFetcher", return_value=paid
    ):
        out = fetch_with_strategy("https://public.example.com/p", ctx=ctx)

    assert out.fetch_tier == "sf_js"
    paid.fetch.assert_called_once()


def test_paid_allowed_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from fetch_strategy import _paid_allowed_for

    with patch("security_url.is_private_host", side_effect=RuntimeError("boom")):
        assert _paid_allowed_for("https://example.com/") is False
