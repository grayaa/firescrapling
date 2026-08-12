#!/usr/bin/env python3
"""
Run from repo root or backend dir:
  python apps/firescrapling/backend/scripts/run_scraping_tests.py
  cd apps/firescrapling/backend && python scripts/run_scraping_tests.py

Uses a local HTTP server (no network) to test crawl, map, and main-content extraction.
"""
from __future__ import annotations

import http.server
import os
import socketserver
import sys
import threading

# Backend package root (parent of scripts/)
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from scraping_engine import (  # noqa: E402
    crawl_bfs_iter,
    extract_links_from_html,
    extract_title_from_html,
    html_to_markdown,
    normalize_http_url,
    same_site,
)


HTML_INDEX = """<!DOCTYPE html>
<html><head><title>Fixture Index</title></head>
<body>
<nav><p>Navigation sidebar noise that should be de-emphasized in main content mode.</p></nav>
<main>
  <h1>Welcome</h1>
  <p>Primary article body for testing.</p>
  <a href="/page2">Page two</a>
  <a href="relative">Relative link</a>
</main>
</body></html>"""

HTML_PAGE2 = """<!DOCTYPE html>
<html><head><title>Page Two</title></head>
<body><main><p>Second page content.</p><a href="/">Home</a></main></body></html>"""

HTML_RELATIVE = """<!DOCTYPE html>
<html><head><title>Relative</title></head>
<body><main><p>Relative path page.</p></main></body></html>"""


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index"):
            body = HTML_INDEX.encode("utf-8")
        elif path == "/page2":
            body = HTML_PAGE2.encode("utf-8")
        elif path == "/relative":
            body = HTML_RELATIVE.encode("utf-8")
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


def _run() -> int:
    failures: list[str] = []

    def ok(name: str) -> None:
        print(f"  OK  {name}")

    def fail(name: str, msg: str) -> None:
        failures.append(f"{name}: {msg}")
        print(f"  FAIL {name}: {msg}")

    # --- Unit-style helpers ---
    u1 = "http://Example.com/path#frag"
    n1 = normalize_http_url(u1)
    if "#" in n1:
        fail("normalize_http_url", "fragment not stripped")
    else:
        ok("normalize_http_url strips fragment")

    if not same_site("https://foo.com/", "https://foo.com/bar", ignore_subdomains=False):
        fail("same_site", "same host should match")
    else:
        ok("same_site same host")

    if not same_site("https://a.foo.com/", "https://b.foo.com/", ignore_subdomains=False):
        fail("same_site", "subdomains of same registrable domain should match when ignore_subdomains=False")
    else:
        ok("same_site registrable domain")

    if same_site("https://a.foo.com/", "https://b.foo.com/", ignore_subdomains=True):
        fail("same_site", "different hosts should not match when ignore_subdomains=True")
    else:
        ok("same_site ignore_subdomains")

    # --- HTML fixtures (no server) ---
    title = extract_title_from_html(HTML_INDEX)
    if "Fixture" not in title:
        fail("extract_title_from_html", title)
    else:
        ok("extract_title_from_html")

    md_main = html_to_markdown(HTML_INDEX, "http://127.0.0.1/", only_main_content=True)
    md_full = html_to_markdown(HTML_INDEX, "http://127.0.0.1/", only_main_content=False)
    if "Welcome" not in md_main:
        fail("html_to_markdown", "main extract missing primary heading")
    else:
        ok("html_to_markdown main-content extract")
    if "Welcome" not in md_full:
        fail("html_to_markdown", "full markdown missing primary heading")
    else:
        ok("html_to_markdown full-page markdownify")

    links = extract_links_from_html(HTML_INDEX, "http://127.0.0.1:9/")
    if not any("/page2" in x for x in links):
        fail("extract_links_from_html", str(links))
    else:
        ok("extract_links_from_html")

    # --- Local server: crawl ---
    with socketserver.TCPServer(("127.0.0.1", 0), FixtureHandler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            seed = base + "/"
            pages: list[dict] = []
            for ev, payload in crawl_bfs_iter(seed, limit=5, max_depth=2, ignore_subdomains=False):
                if ev == "page":
                    pages.append(payload)
                elif ev == "done":
                    if payload["count"] < 2:
                        fail("crawl_bfs_iter", f"expected >=2 pages, got {payload['count']} errors={payload['errors']}")
                    else:
                        ok(f"crawl_bfs_iter ({payload['count']} pages)")
            urls = {p["url"] for p in pages}
            if not any("/page2" in u for u in urls):
                fail("crawl_bfs_iter", f"missing /page2 in {urls}")
            import main as core  # noqa: E402

            m = core.map_domain(seed, None, None, False)
            if not m.get("success"):
                fail("map_domain", str(m))
            else:
                ml = m.get("links") or []
                if not any("/page2" in x for x in ml):
                    fail("map_domain", f"missing page2 in {ml}")
                else:
                    ok("map_domain")

        finally:
            httpd.shutdown()
            thread.join(timeout=2)

    if failures:
        print("\n--- Failures ---")
        for f in failures:
            print(f)
        return 1
    print("\nAll scraping engine tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
