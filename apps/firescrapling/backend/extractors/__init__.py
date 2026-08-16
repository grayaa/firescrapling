"""Extractor registry — domain matcher → Extractor."""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse

from extractors.anime3rb import Anime3rbExtractor
from extractors.base import Extractor
from extractors.reelshort import ReelshortExtractor

_EXTRACTORS: List[Extractor] = [
    Anime3rbExtractor(),
    ReelshortExtractor(),
]


def register(extractor: Extractor) -> None:
    _EXTRACTORS.append(extractor)


def list_extractors() -> List[Extractor]:
    return list(_EXTRACTORS)


def supported_sites() -> List[dict]:
    out = []
    for ex in _EXTRACTORS:
        out.append(
            {
                "name": ex.name,
                "domains": list(ex.domains),
                "needs_network_capture": bool(getattr(ex, "needs_network_capture", False)),
                "note": "Returns manifest/poster/page URLs only — does not proxy media.",
            }
        )
    return out


def find_extractor(url: str) -> Optional[Extractor]:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for ex in _EXTRACTORS:
        if ex.matches(url):
            return ex
        for d in ex.domains:
            d = d.lower()
            if host == d or host.endswith("." + d):
                return ex
    return None
