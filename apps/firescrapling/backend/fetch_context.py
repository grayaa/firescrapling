"""Per-request fetch identity — never read process-global API keys for BYOK paths."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

ProviderName = Literal["scrapedo", "scrapfly", "local"]
CredentialSource = Literal["byok", "platform", "local"]


@dataclass(frozen=True)
class FetchContext:
    provider: ProviderName
    api_key: Optional[str]
    proxy_pool: Optional[str]
    residential_pool: Optional[str]
    country: Optional[str]
    source: CredentialSource
    credential_id: Optional[str]

    @property
    def can_use_paid(self) -> bool:
        return self.provider in ("scrapedo", "scrapfly") and bool(self.api_key)

    def paid_pool(self, *, residential: bool = False) -> Optional[str]:
        if residential:
            return self.residential_pool or "public_residential_pool"
        if self.proxy_pool and "residential" in self.proxy_pool.lower():
            return "public_datacenter_pool"
        return self.proxy_pool or "public_datacenter_pool"
