"""Crawl concurrency caps and pagination helpers."""
from __future__ import annotations

from scraping_engine import crawl_concurrency_caps


def test_crawl_concurrency_defaults(monkeypatch) -> None:
    monkeypatch.delenv("CRAWL_GLOBAL_CONCURRENCY", raising=False)
    monkeypatch.delenv("CRAWL_PER_HOST_CONCURRENCY", raising=False)
    g, h = crawl_concurrency_caps()
    assert g == 4
    assert h == 2


def test_crawl_concurrency_env(monkeypatch) -> None:
    monkeypatch.setenv("CRAWL_GLOBAL_CONCURRENCY", "8")
    monkeypatch.setenv("CRAWL_PER_HOST_CONCURRENCY", "3")
    g, h = crawl_concurrency_caps()
    assert g == 8
    assert h == 3


def test_per_host_capped_by_global(monkeypatch) -> None:
    monkeypatch.setenv("CRAWL_GLOBAL_CONCURRENCY", "2")
    monkeypatch.setenv("CRAWL_PER_HOST_CONCURRENCY", "9")
    g, h = crawl_concurrency_caps()
    assert g == 2
    assert h == 2


def test_crawl_status_pagination(authed, fixture_server, monkeypatch) -> None:
    monkeypatch.setenv("API_ALLOW_PRIVATE_URLS", "true")
    client, _key, _session = authed
    # Start a tiny crawl against the fixture server
    r = client.post("/v1/crawl", json={"url": fixture_server + "/", "limit": 2, "maxDepth": 1})
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]

    import time

    for _ in range(40):
        st = client.get(f"/v1/crawl/{job_id}", params={"offset": 0, "limit": 1})
        assert st.status_code == 200
        body = st.json()
        assert "pagination" in body
        if body["status"] in ("completed", "failed"):
            break
        time.sleep(0.25)
    else:
        raise AssertionError("crawl did not finish")

    body = client.get(f"/v1/crawl/{job_id}", params={"offset": 0, "limit": 1}).json()
    assert body["pagination"]["limit"] == 1
    assert body["pagination"]["offset"] == 0
    assert isinstance(body["pagination"]["total"], int)
    assert len(body["data"]) <= 1
