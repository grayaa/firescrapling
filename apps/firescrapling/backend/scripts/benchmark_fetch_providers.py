#!/usr/bin/env python3
"""Benchmark Scrapfly vs Scrape.do on shared tiers (static / js / hard).

Usage (from repo, via Compose):
  docker compose run --rm -e SCRAPFLY_API_KEY -e SCRAPE_API_KEY backend \\
    python scripts/benchmark_fetch_providers.py

Env:
  SCRAPFLY_API_KEY, SCRAPE_API_KEY (or SCRAPE_DO_API_KEY)
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import requests

TARGETS = [
    ("easy", "https://example.com/"),
    ("docs", "https://httpbin.org/html"),
    ("spa_js", "https://www.reelshort.com/"),
    ("cf_hard", "https://anime3rb.com/titles/list"),
]

MODES = ("static", "js", "hard")


@dataclass
class Row:
    provider: str
    mode: str
    label: str
    url: str
    ok: bool
    http_status: Optional[int]
    latency_ms: int
    html_len: int
    text_len: int
    credits: Optional[float]
    credits_note: str
    error: str = ""
    title_snip: str = ""


def _strip_text(html: str) -> str:
    t = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html or "")
    t = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", t)
    t = re.sub(r"(?is)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _title(html: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    return (m.group(1).strip()[:80] if m else "")[:80]


def _usable(html: str, status: Optional[int]) -> bool:
    if status is None or status >= 400:
        return False
    low = (html or "").lower()
    if "just a moment" in low and "cloudflare" in low:
        return False
    return len(_strip_text(html)) >= 80


def scrape_do(
    token: str,
    url: str,
    *,
    mode: str,
    timeout: int = 120,
) -> Dict[str, Any]:
    params: Dict[str, str] = {"token": token, "url": url}
    if mode == "js":
        params["render"] = "true"
    elif mode == "hard":
        params["render"] = "true"
        params["super"] = "true"
    # static: neither
    t0 = time.perf_counter()
    r = requests.get("https://api.scrape.do/", params=params, timeout=timeout)
    ms = int((time.perf_counter() - t0) * 1000)
    html = r.text or ""
    # Common credit headers (best-effort across API versions)
    credits = None
    note = ""
    for hk, hv in r.headers.items():
        lk = hk.lower()
        if "credit" in lk or "cost" in lk or "concurrency" in lk:
            note += f"{hk}={hv}; "
            try:
                if credits is None and re.search(r"^\d+(\.\d+)?$", str(hv).strip()):
                    credits = float(hv)
            except ValueError:
                pass
    # Scrape.do often reports Remaining-Requests
    rem = r.headers.get("Remaining-Requests") or r.headers.get("remaining-requests")
    if rem is not None:
        note += f"Remaining-Requests={rem}; "
    return {
        "status": r.status_code,
        "html": html,
        "ms": ms,
        "credits": credits,
        "credits_note": note.strip() or "n/a (pay-for-success if 2xx)",
        "error": "" if r.ok else html[:240],
    }


def scrapfly(
    key: str,
    url: str,
    *,
    mode: str,
    timeout: int = 150,
) -> Dict[str, Any]:
    from scrapfly import ScrapeConfig, ScrapflyClient

    kwargs: Dict[str, Any] = {
        "url": url,
        "render_js": mode in ("js", "hard"),
        "asp": mode == "hard",
        "raise_on_upstream_error": False,
        "retry": mode == "hard",
    }
    if mode == "hard":
        kwargs["proxy_pool"] = "public_residential_pool"
        if kwargs["render_js"]:
            kwargs["rendering_wait"] = 3000
    elif mode == "js":
        kwargs["proxy_pool"] = "public_datacenter_pool"
        kwargs["rendering_wait"] = 2000
    else:
        kwargs["proxy_pool"] = "public_datacenter_pool"
        kwargs["timeout"] = 60000

    client = ScrapflyClient(key=key)
    t0 = time.perf_counter()
    try:
        api = client.scrape(ScrapeConfig(**kwargs))
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return {
            "status": None,
            "html": "",
            "ms": ms,
            "credits": None,
            "credits_note": "request failed",
            "error": f"{type(e).__name__}: {e}"[:400],
        }
    ms = int((time.perf_counter() - t0) * 1000)
    result = getattr(api, "scrape_result", None) or {}
    if not isinstance(result, dict):
        result = {}
    content = result.get("content") or ""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    status = result.get("status_code")
    # cost may be on api.cost or context
    cost = None
    note = ""
    try:
        c = getattr(api, "cost", None)
        if c is not None:
            if isinstance(c, dict):
                cost = float(c.get("total") or c.get("cost") or 0) or None
                note = json.dumps(c)[:200]
            else:
                cost = float(c)
                note = f"cost={c}"
    except Exception:
        pass
    ctx = getattr(api, "context", None) or {}
    if isinstance(ctx, dict) and ctx.get("cost"):
        note += f" context.cost={ctx.get('cost')}"
        try:
            if cost is None:
                cc = ctx["cost"]
                cost = float(cc.get("total") if isinstance(cc, dict) else cc)
        except Exception:
            pass
    err = ""
    if result.get("error"):
        err = str(result.get("error"))[:300]
        note += f" error={err}"
    return {
        "status": int(status) if status is not None else None,
        "html": str(content),
        "ms": ms,
        "credits": cost,
        "credits_note": note or "see Scrapfly dashboard log",
        "error": err,
    }


def run_one(provider: str, mode: str, label: str, url: str, keys: Dict[str, str]) -> Row:
    try:
        if provider == "scrapfly":
            if not keys.get("scrapfly"):
                return Row(provider, mode, label, url, False, None, 0, 0, 0, None, "no key", "missing SCRAPFLY_API_KEY")
            raw = scrapfly(keys["scrapfly"], url, mode=mode)
        else:
            if not keys.get("scrapedo"):
                return Row(provider, mode, label, url, False, None, 0, 0, 0, None, "no key", "missing SCRAPE_API_KEY")
            raw = scrape_do(keys["scrapedo"], url, mode=mode)
    except Exception as e:
        return Row(provider, mode, label, url, False, None, 0, 0, 0, None, "exception", f"{type(e).__name__}: {e}"[:300])

    html = raw["html"]
    status = raw["status"]
    ok = _usable(html, status) and not raw.get("error")
    # Scrape.do: only successful (2xx/400/404/410) consume credits.
    # Published ballpark: datacenter ~1, residential+JS ~25 (see scrape.do docs).
    credits = raw.get("credits")
    note = raw.get("credits_note") or ""
    if provider == "scrapedo" and credits is None and status in (200, 201, 400, 404, 410):
        est = {"static": 1.0, "js": 5.0, "hard": 25.0}.get(mode, 1.0)
        credits = est
        note = (note + f" | est_credits≈{est} by mode").strip(" |")
    return Row(
        provider=provider,
        mode=mode,
        label=label,
        url=url,
        ok=ok,
        http_status=status,
        latency_ms=int(raw["ms"]),
        html_len=len(html or ""),
        text_len=len(_strip_text(html)),
        credits=credits,
        credits_note=note,
        error=(raw.get("error") or "")[:200],
        title_snip=_title(html),
    )


def main() -> None:
    keys = {
        "scrapfly": (os.environ.get("SCRAPFLY_API_KEY") or "").strip(),
        "scrapedo": (
            os.environ.get("SCRAPE_API_KEY")
            or os.environ.get("SCRAPE_DO_API_KEY")
            or ""
        ).strip(),
    }
    print("keys scrapfly=", bool(keys["scrapfly"]), "scrapedo=", bool(keys["scrapedo"]))
    rows: List[Row] = []
    providers = []
    if keys["scrapfly"]:
        providers.append("scrapfly")
    if keys["scrapedo"]:
        providers.append("scrapedo")
    if not providers:
        raise SystemExit("No API keys set")

    for label, url in TARGETS:
        for mode in MODES:
            for provider in providers:
                print(f"→ {provider:9} {mode:6} {label:8} {url}")
                row = run_one(provider, mode, label, url, keys)
                rows.append(row)
                print(
                    f"  ok={row.ok} status={row.http_status} "
                    f"text={row.text_len} ms={row.latency_ms} credits={row.credits} "
                    f"title={row.title_snip!r} err={row.error[:80]!r}"
                )
                time.sleep(0.4)

    # Summary table
    print("\n=== SUMMARY ===")
    hdr = f"{'provider':9} {'mode':6} {'label':8} {'ok':3} {'status':6} {'text':6} {'ms':6} {'credits':8}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(
            f"{r.provider:9} {r.mode:6} {r.label:8} "
            f"{'Y' if r.ok else 'N':3} {str(r.http_status or '-'):6} "
            f"{r.text_len:6} {r.latency_ms:6} {str(r.credits if r.credits is not None else '-'):8}"
        )

    # Aggregate
    print("\n=== BY PROVIDER ===")
    for p in providers:
        subset = [r for r in rows if r.provider == p]
        ok_n = sum(1 for r in subset if r.ok)
        known_credits = [r.credits for r in subset if r.credits is not None]
        avg_ms = int(sum(r.latency_ms for r in subset) / max(1, len(subset)))
        print(
            f"{p}: {ok_n}/{len(subset)} ok, avg_latency={avg_ms}ms, "
            f"sum_known_credits={sum(known_credits) if known_credits else 'n/a'}"
        )

    out_path = os.environ.get("BENCH_OUT") or "/tmp/fetch_benchmark.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in rows], f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
