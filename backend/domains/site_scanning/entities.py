from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ScanStatus(StrEnum):
    COMPLETED = "completed"
    REJECTED = "rejected"


class ScanStopReason(StrEnum):
    COMPLETED = "completed"
    DEPTH_LIMIT = "depth_limit"
    PAGE_LIMIT = "page_limit"
    RUNTIME_LIMIT = "runtime_limit"
    DOMAIN_LIMIT = "domain_limit"
    INVALID_URL = "invalid_url"


@dataclass(frozen=True)
class CrawlPolicy:
    max_depth: int = 1
    max_pages: int = 50
    max_runtime_seconds: int = 300
    same_domain_only: bool = True
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    per_host_concurrency: int = 1

    def normalized(self) -> "CrawlPolicy":
        max_depth = max(0, min(self.max_depth, 3))
        max_pages = max(1, min(self.max_pages, 250))
        max_runtime_seconds = max(30, min(self.max_runtime_seconds, 1800))
        per_host_concurrency = max(1, min(self.per_host_concurrency, 4))
        return CrawlPolicy(
            max_depth=max_depth,
            max_pages=max_pages,
            max_runtime_seconds=max_runtime_seconds,
            same_domain_only=self.same_domain_only,
            allowed_hosts=frozenset(host.lower() for host in self.allowed_hosts),
            per_host_concurrency=per_host_concurrency,
        )


@dataclass(frozen=True)
class CrawlCandidate:
    source_url: str
    title: str
    depth: int
    parent_url: str | None
    normalized_url: str
    inclusion_reason: str
    status: str
    confidence: float
    evidence: tuple[str, ...] = ()
    external_model_id: str | None = None


@dataclass(frozen=True)
class CrawlRejection:
    source_url: str
    reason: str
    depth: int
    parent_url: str | None = None


@dataclass(frozen=True)
class ScanSummary:
    status: ScanStatus
    stop_reason: ScanStopReason
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


@dataclass(frozen=True)
class ScanResult:
    summary: ScanSummary
    candidates: tuple[CrawlCandidate, ...]
    rejections: tuple[CrawlRejection, ...]
