from __future__ import annotations

from pydantic import BaseModel


class SiteScanAdapterResponse(BaseModel):
    site_key: str
    display_name: str
    enabled: bool
    supports_downloads: bool
    allowed_hosts: list[str]
    default_limits: dict
    robots_terms_notes: str | None


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
