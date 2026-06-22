from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from backend.domains.site_scanning.entities import CrawlCandidate


@dataclass(frozen=True)
class SiteAdapterDeclaration:
    site_key: str
    display_name: str
    allowed_hosts: tuple[str, ...]
    browser_session_hosts: tuple[str, ...] = ()
    browser_session_observe_hosts: tuple[str, ...] = ()
    browser_session_required_cookie_names: tuple[str, ...] = ()
    base_url: str | None = None
    login_url: str | None = None
    enabled: bool = True
    supports_downloads: bool = False
    supported_auth_modes: tuple[str, ...] = ("none",)
    auth_storage_notes: str | None = None
    default_limits: dict = field(default_factory=dict)
    robots_terms_notes: str | None = None


@dataclass(frozen=True)
class AdapterDiscoveryResult:
    candidates: tuple[CrawlCandidate, ...]
    discovered_urls: tuple[str, ...]


class SiteScanAdapter(Protocol):
    site_key: str
    display_name: str
    allowed_hosts: frozenset[str]
    supports_downloads: bool

    def discover(
        self,
        url: str,
        depth: int,
        parent_url: str | None,
        auth_headers: dict[str, str] | None = None,
    ) -> AdapterDiscoveryResult:
        """Return metadata candidates and child URLs allowed by this adapter."""
