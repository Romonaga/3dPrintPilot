from __future__ import annotations

from pydantic import BaseModel


class SiteScanAdapterResponse(BaseModel):
    site_key: str
    display_name: str
    base_url: str | None
    login_url: str | None
    enabled: bool
    supports_downloads: bool
    supported_auth_modes: list[str]
    auth_storage_notes: str | None
    allowed_hosts: list[str]
    default_limits: dict
    robots_terms_notes: str | None


class SiteAuthProfileResponse(BaseModel):
    site_key: str
    display_name: str
    auth_mode: str
    label: str | None
    account_identifier: str | None
    masked_account_identifier: str | None
    header_name: str | None
    configured: bool
    enabled: bool
    auth_ready: bool
    link_status: str
    link_status_message: str
    masked_value: str | None
    updated_at: str | None


class SiteAuthLinkResponse(BaseModel):
    site_key: str
    display_name: str
    auth_mode: str
    login_url: str | None
    account_identifier: str | None
    instructions: list[str]
    storage_notes: str


class SiteAuthReadinessResponse(BaseModel):
    site_key: str
    display_name: str
    auth_mode: str
    auth_ready: bool
    link_status: str
    message: str
    configured: bool
    enabled: bool
    masked_account_identifier: str | None
    masked_value: str | None
    updated_at: str | None


class SiteScanSummaryResponse(BaseModel):
    scan_run_id: int | None = None
    status: str
    stop_reason: str
    start_url: str
    normalized_start_url: str | None
    site_key: str
    max_depth: int
    max_pages: int
    max_runtime_seconds: int
    same_domain_only: bool
    per_host_concurrency: int
    queued_url_count: int
    scanned_url_count: int
    accepted_result_count: int
    rejected_url_count: int
    duration_ms: int


class SiteScanCandidateResponse(BaseModel):
    source_url: str
    title: str
    depth: int
    parent_url: str | None
    normalized_url: str
    inclusion_reason: str
    status: str
    confidence: float
    evidence: list[str]
    license: str | None
    attribution: str | None
    requirements: dict


class SiteScanRejectionResponse(BaseModel):
    source_url: str
    reason: str
    depth: int
    parent_url: str | None


class SiteScanResponse(BaseModel):
    summary: SiteScanSummaryResponse
    candidates: list[SiteScanCandidateResponse]
    rejections: list[SiteScanRejectionResponse]
