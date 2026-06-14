from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.domains.site_scanning.entities import CrawlCandidate


@dataclass(frozen=True)
class AdapterDiscoveryResult:
    candidates: tuple[CrawlCandidate, ...]
    discovered_urls: tuple[str, ...]


class SiteScanAdapter(Protocol):
    site_key: str
    display_name: str
    allowed_hosts: frozenset[str]
    supports_downloads: bool

    def discover(self, url: str, depth: int, parent_url: str | None) -> AdapterDiscoveryResult:
        """Return metadata candidates and child URLs allowed by this adapter."""
