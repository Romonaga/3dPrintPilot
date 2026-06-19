from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.domains.site_scanning.entities import CrawlPolicy, ScanResult
from backend.domains.site_scanning.schemas.request import SiteScanRequest
from backend.domains.site_scanning.schemas.response import (
    SiteScanAdapterResponse,
    SiteScanCandidateResponse,
    SiteScanRejectionResponse,
    SiteScanResponse,
    SiteScanSummaryResponse,
)
from backend.domains.site_scanning.service import SiteScanService
from backend.domains.site_scanning.store import SiteScanStore
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/site-scanning", tags=["site-scanning"])
service = SiteScanService()


def get_site_scan_store(session: Session = Depends(get_db_session)) -> SiteScanStore:
    return SiteScanStore(session)


@router.get("/adapters", response_model=list[SiteScanAdapterResponse])
def list_adapters(_user=Depends(require_roles("viewer"))) -> list[SiteScanAdapterResponse]:
    return [
        SiteScanAdapterResponse(
            site_key=adapter.site_key,
            display_name=adapter.display_name,
            supports_downloads=adapter.supports_downloads,
        )
        for adapter in service.list_adapters()
    ]


@router.post("/scans", response_model=SiteScanResponse)
def create_scan(
    request: SiteScanRequest,
    _user=Depends(require_roles("user")),
    store: SiteScanStore = Depends(get_site_scan_store),
) -> SiteScanResponse:
    try:
        result = service.scan(
            start_url=request.url,
            site_key=request.site_key,
            policy=CrawlPolicy(
                max_depth=request.max_depth,
                max_pages=request.max_pages,
                max_runtime_seconds=request.max_runtime_seconds,
                same_domain_only=request.same_domain_only,
                allowed_hosts=frozenset(request.allowed_hosts),
                per_host_concurrency=request.per_host_concurrency,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    scan_run = store.save_scan_result(result)
    return _to_response(result, scan_run_id=scan_run.id)


def _to_response(result: ScanResult, scan_run_id: int | None = None) -> SiteScanResponse:
    summary = result.summary
    return SiteScanResponse(
        summary=SiteScanSummaryResponse(
            scan_run_id=scan_run_id,
            status=summary.status.value,
            stop_reason=summary.stop_reason.value,
            start_url=summary.start_url,
            normalized_start_url=summary.normalized_start_url,
            site_key=summary.site_key,
            max_depth=summary.max_depth,
            max_pages=summary.max_pages,
            max_runtime_seconds=summary.max_runtime_seconds,
            same_domain_only=summary.same_domain_only,
            per_host_concurrency=summary.per_host_concurrency,
            queued_url_count=summary.queued_url_count,
            scanned_url_count=summary.scanned_url_count,
            accepted_result_count=summary.accepted_result_count,
            rejected_url_count=summary.rejected_url_count,
            duration_ms=summary.duration_ms,
        ),
        candidates=[
            SiteScanCandidateResponse(
                source_url=candidate.source_url,
                title=candidate.title,
                depth=candidate.depth,
                parent_url=candidate.parent_url,
                normalized_url=candidate.normalized_url,
                inclusion_reason=candidate.inclusion_reason,
                status=candidate.status,
                confidence=candidate.confidence,
                evidence=list(candidate.evidence),
            )
            for candidate in result.candidates
        ],
        rejections=[
            SiteScanRejectionResponse(
                source_url=rejection.source_url,
                reason=rejection.reason,
                depth=rejection.depth,
                parent_url=rejection.parent_url,
            )
            for rejection in result.rejections
        ],
    )
