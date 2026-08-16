"""Media extractor protocol and shared types.

Extractors return stream/poster/page *URLs only* — they never proxy, download,
or rehost media bytes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Protocol, runtime_checkable

Kind = Literal["series", "episode", "catalog", "unknown"]


@runtime_checkable
class Extractor(Protocol):
    name: str
    domains: List[str]
    needs_network_capture: bool

    def matches(self, url: str) -> bool: ...

    def extract(self, html: str, url: str, page: Optional[Dict[str, Any]] = None) -> Dict[str, Any]: ...


def empty_result(
    *,
    kind: Kind = "unknown",
    extractor: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "success": True,
        "kind": kind,
        "data": data or {},
        "extractor": extractor,
    }
