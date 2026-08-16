"""reelshort.com — covers, episode list, HLS .m3u8 URLs when present in HTML.

Note: many ReelShort .m3u8 URLs appear only after player XHR. When absent from
HTML, `stream` is null and `needs_network_capture` signals a future Playwright
capture_network mode (not implemented in this scaffold).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from extractors.base import empty_result


class ReelshortExtractor:
    name = "reelshort"
    domains = ["reelshort.com"]
    needs_network_capture = True

    def matches(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host == "reelshort.com" or host.endswith(".reelshort.com")

    def extract(self, html: str, url: str, page: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        soup = BeautifulSoup(html or "", "html.parser")
        path = (urlparse(url).path or "/").rstrip("/") or "/"

        # Episode / watch page
        if any(x in path for x in ("/episode", "/watch", "/play", "/ep/")):
            return self._parse_episode(soup, url, html)

        # Series detail
        if "/movie" in path or "/drama" in path or "/detail" in path or re.search(r"/[a-z0-9-]{8,}", path):
            series = self._parse_series(soup, url, html)
            if series["data"].get("episodes") or series["data"].get("title"):
                return series

        # Homepage / catalog
        return empty_result(
            kind="catalog",
            extractor=self.name,
            data={"items": self._parse_catalog(soup, url)},
        )

    def _abs(self, base: str, href: Optional[str]) -> Optional[str]:
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            return None
        return urljoin(base, href)

    def _find_m3u8(self, html: str) -> List[str]:
        found = re.findall(r"""https?://[^"'\\s<>]+?\.m3u8[^"'\\s<>]*""", html or "", re.I)
        # also escaped JSON forms
        found += re.findall(r"""https?:\\?/\\?/[^"'\\s<>]+?\.m3u8[^"'\\s<>]*""", html or "", re.I)
        cleaned = []
        for u in found:
            u = u.replace("\\/", "/")
            if u not in cleaned:
                cleaned.append(u)
        return cleaned

    def _parse_catalog(self, soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for a in soup.select("a[href]"):
            href = self._abs(url, a.get("href"))
            if not href or href in seen:
                continue
            img = a.find("img")
            if not img:
                continue
            title = (
                a.get("title")
                or img.get("alt")
                or a.get_text(" ", strip=True)
                or ""
            ).strip()
            if not title:
                continue
            seen.add(href)
            poster = self._abs(url, img.get("data-src") or img.get("src"))
            items.append({"title": title, "page_url": href, "poster": poster})
        return items[:100]

    def _parse_series(self, soup: BeautifulSoup, url: str, html: str) -> Dict[str, Any]:
        title_el = soup.find("h1") or soup.find("title")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        poster = None
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            poster = self._abs(url, og["content"])

        episodes: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for a in soup.select("a[href*='episode'], a[href*='ep'], a[href*='watch']"):
            href = self._abs(url, a.get("href"))
            if not href or href in seen:
                continue
            seen.add(href)
            label = a.get_text(" ", strip=True) or ""
            num_m = re.search(r"(\d+)", label) or re.search(r"(?:ep|episode)[-_/]?(\d+)", href, re.I)
            number = int(num_m.group(1)) if num_m else len(episodes) + 1
            episodes.append(
                {
                    "number": number,
                    "title": label or f"Episode {number}",
                    "page_url": href,
                    "stream": None,
                }
            )
        episodes.sort(key=lambda e: e["number"])

        # If page itself embeds an m3u8, attach to first episode or as series-level
        m3u8s = self._find_m3u8(html)
        if m3u8s and episodes:
            episodes[0]["stream"] = {"type": "hls", "url": m3u8s[0]}

        return empty_result(
            kind="series",
            extractor=self.name,
            data={"title": title, "poster": poster, "page_url": url, "episodes": episodes},
        )

    def _parse_episode(self, soup: BeautifulSoup, url: str, html: str) -> Dict[str, Any]:
        title_el = soup.find("h1") or soup.find("title")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        m3u8s = self._find_m3u8(html)
        streams = [{"type": "hls", "url": u} for u in m3u8s]
        # video/source fallbacks
        for tag in soup.find_all(["video", "source", "iframe"]):
            for attr in ("src", "data-src"):
                val = tag.get(attr)
                abs_u = self._abs(url, val) if val else None
                if abs_u and abs_u not in {s["url"] for s in streams}:
                    low = abs_u.lower()
                    stype = "hls" if ".m3u8" in low else "file"
                    streams.append({"type": stype, "url": abs_u})

        primary = streams[0] if streams else None
        return empty_result(
            kind="episode",
            extractor=self.name,
            data={
                "title": title,
                "page_url": url,
                "stream": primary,
                "streams": streams,
                "capture_hint": (
                    None
                    if primary
                    else "m3u8 often loaded via XHR after player init; needs capture_network fetch mode"
                ),
            },
        )
