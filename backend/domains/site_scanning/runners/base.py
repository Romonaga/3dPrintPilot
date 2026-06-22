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
class SourceSiteFile:
    file_id: str
    filename: str
    file_format: str
    size_bytes: int | None
    source_file_url: str
    supported_model_file: bool
    created_at: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class SourceSiteProjectFiles:
    site_key: str
    source_project_url: str
    external_project_id: str
    project_title: str | None
    files: tuple[SourceSiteFile, ...]


@dataclass(frozen=True)
class SourceSiteDownloadedFile:
    file_id: str
    filename: str
    content_type: str | None
    data: bytes
    source_project_url: str
    source_file_url: str


class SourceSiteRunnerError(RuntimeError):
    """Raised when a supported source site cannot complete a runner operation."""


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

    def list_project_files(
        self,
        project_url: str,
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> SourceSiteProjectFiles:
        """Return files exposed by a supported project URL."""

    def download_project_file(
        self,
        project_url: str,
        file_id: str,
        *,
        auth_headers: dict[str, str] | None = None,
        max_bytes: int,
    ) -> SourceSiteDownloadedFile:
        """Download a selected project file without exposing site credentials."""
