from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class SourceSiteCapability(StrEnum):
    PUBLIC_SCAN = "public_scan"
    ACCOUNT_SETUP = "account_setup"
    PROJECT_LOOKUP = "project_lookup"
    FILE_LISTING = "file_listing"
    FILE_DOWNLOAD = "file_download"
    LICENSE_METADATA = "license_metadata"


class SourceSiteSupportLevel(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    GENERIC_ONLY = "generic_only"
    PLANNED = "planned"


@dataclass(frozen=True)
class SourceSiteProjectRef:
    source_url: str
    external_project_id: str | None = None
    slug: str | None = None


@dataclass(frozen=True)
class SourceSiteRunnerManifest:
    site_key: str
    display_name: str
    support_level: SourceSiteSupportLevel
    capabilities: tuple[SourceSiteCapability, ...]
    allowed_hosts: tuple[str, ...]
    url_patterns: tuple[str, ...] = ()
    browser_session_hosts: tuple[str, ...] = ()
    browser_session_observe_hosts: tuple[str, ...] = ()
    browser_session_required_cookie_names: tuple[str, ...] = ()
    base_url: str | None = None
    login_url: str | None = None
    setup_required: bool = False
    supports_downloads: bool = False
    supported_auth_modes: tuple[str, ...] = ("none",)
    auth_storage_notes: str | None = None
    default_limits: dict = field(default_factory=dict)
    robots_terms_notes: str | None = None

    @property
    def is_generic_only(self) -> bool:
        return self.support_level == SourceSiteSupportLevel.GENERIC_ONLY


class SourceSiteRunner(Protocol):
    manifest: SourceSiteRunnerManifest

    def identify_project(self, url: str) -> SourceSiteProjectRef | None:
        """Return a normalized project reference when this runner understands the URL."""
