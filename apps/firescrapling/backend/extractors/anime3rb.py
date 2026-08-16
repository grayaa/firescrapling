"""anime3rb.com — titles list, title detail, episode/player links (URLs only)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from extractors.base import empty_result


class Anime3rbExtractor:
    name = "anime3rb"
    domains = ["anime3rb.com"]
    needs_network_capture = False

    def matches(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host == "anime3rb.com" or host.endswith(".anime3rb.com")

    def extract(self, html: str, url: str, page: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        soup = BeautifulSoup(html or "", "html.parser")
        path = (urlparse(url).path or "/").rstrip("/") or "/"

        # Episode / player page (check before catalog — paths may contain /titles/)
        if "/episode" in path or re.search(r"/ep(?:isode)?[-_/]?\d+", path, re.I):
            return self._parse_episode(soup, url, html or "")

        # Catalog / titles list only (not /titles/<slug>)
        if path in ("/", "/titles", "/titles/list") or path.endswith("/titles/list"):
            items = self._parse_catalog(soup, url)
            return empty_result(kind="catalog", extractor=self.name, data={"items": items})

        # Title detail (default for /titles/<slug> and similar)
        return self._parse_series(soup, url)

    def _abs(self, base: str, href: Optional[str]) -> Optional[str]:
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            return None
        return urljoin(base, href)

    def _parse_catalog(self, soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for a in soup.select("a[href*='/title'], a[href*='/titles/']"):
            href = self._abs(url, a.get("href"))
            if not href or href in seen:
                continue
            if "/titles/list" in href:
                continue
            title = (a.get_text(" ", strip=True) or a.get("title") or "").strip()
            if not title:
                continue
            seen.add(href)
            img = a.find("img")
            poster = None
            if img:
                poster = self._abs(url, img.get("data-src") or img.get("src"))
            items.append({"title": title, "page_url": href, "poster": poster})
        return items

    def _parse_series(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        title_el = soup.find("h1") or soup.find("title")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        poster = None
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            poster = self._abs(url, og["content"])
        if not poster:
            img = soup.select_one("img.poster, .poster img, img[src*='poster']")
            if img:
                poster = self._abs(url, img.get("data-src") or img.get("src"))

        episodes: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for a in soup.select("a[href*='episode'], a[href*='/ep']"):
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
        return empty_result(
            kind="series",
            extractor=self.name,
            data={"title": title, "poster": poster, "page_url": url, "episodes": episodes},
        )

    def _parse_episode(self, soup: BeautifulSoup, url: str, html: str = "") -> Dict[str, Any]:
        title_el = soup.find("h1") or soup.find("title")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        streams: List[Dict[str, str]] = []
        # iframe / video / source / data attributes that look like media URLs
        for tag in soup.find_all(["iframe", "video", "source", "a"]):
            for attr in ("src", "data-src", "href", "data-url", "data-file"):
                val = tag.get(attr)
                if not val:
                    continue
                abs_u = self._abs(url, val)
                if not abs_u:
                    continue
                low = abs_u.lower()
                if any(x in low for x in (".m3u8", ".mpd", ".mp4", "player", "embed", "stream")):
                    stype = "hls" if ".m3u8" in low else ("dash" if ".mpd" in low else "file")
                    streams.append({"type": stype, "url": abs_u})

        blob = html or str(soup)
        for m in re.finditer(r"https?://[^\s\"'<>]+?\.(?:m3u8|mpd|mp4)(?:\?[^\s\"'<>]*)?", blob, re.I):
            u = m.group(0)
            stype = "hls" if ".m3u8" in u.lower() else ("dash" if ".mpd" in u.lower() else "file")
            streams.append({"type": stype, "url": u})

        # de-dupe; prefer HLS/DASH manifests over generic embed URLs
        uniq: List[Dict[str, str]] = []
        seen: set[str] = set()
        for s in streams:
            if s["url"] not in seen:
                seen.add(s["url"])
                uniq.append(s)
        uniq.sort(
            key=lambda s: 0 if s["type"] == "hls" else (1 if s["type"] == "dash" else 2)
        )

        primary = uniq[0] if uniq else None
        return empty_result(
            kind="episode",
            extractor=self.name,
            data={
                "title": title,
                "page_url": url,
                "stream": primary,
                "streams": uniq,
            },
        )
