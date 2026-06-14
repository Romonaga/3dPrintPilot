from __future__ import annotations

from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.domains.compatibility.schemas.request import RunCompatibilityChecksRequest
from backend.domains.compatibility.schemas.response import (
    CompatibilityCheckItemResponse,
    CompatibilityCheckResponse,
    CompatibilityRunResponse,
)
from backend.domains.compatibility.service import check_compatibility
from backend.domains.compatibility.store import CompatibilityStore, printer_capabilities, scan_result_requirements

router = APIRouter(prefix="/compatibility", tags=["compatibility"])


def get_compatibility_store(session: Session = Depends(get_db_session)) -> CompatibilityStore:
    return CompatibilityStore(session)


@router.post("/checks", response_model=CompatibilityRunResponse)
def run_compatibility_checks(
    request: RunCompatibilityChecksRequest,
    store: CompatibilityStore = Depends(get_compatibility_store),
) -> CompatibilityRunResponse:
    candidates = store.list_candidate_results(request.scan_run_id, request.max_candidates)
    if not candidates:
        raise HTTPException(status_code=404, detail="No model candidates found for scan run")
    printers = store.list_printers(request.printer_ids)
    if not printers:
        raise HTTPException(status_code=404, detail="No known printers found")

    checks = []
    for candidate in candidates:
        requirements = scan_result_requirements(candidate)
        for printer in printers:
            started = perf_counter()
            report = check_compatibility(printer_capabilities(printer), requirements)
            duration_ms = int((perf_counter() - started) * 1000)
            checks.append(
                store.save_report(
                    scan_result=candidate,
                    printer=printer,
                    report=report,
                    requirements=requirements,
                    duration_ms=duration_ms,
                )
            )
    return CompatibilityRunResponse(
        scan_run_id=request.scan_run_id,
        printer_count=len(printers),
        candidate_count=len(candidates),
        check_count=len(checks),
        checks=[_check_response(check) for check in checks],
    )


@router.get("/checks", response_model=list[CompatibilityCheckResponse])
def list_recent_compatibility_checks(
    limit: int = 50,
    store: CompatibilityStore = Depends(get_compatibility_store),
) -> list[CompatibilityCheckResponse]:
    return [_check_response(check) for check in store.list_recent_checks(max(1, min(limit, 100)))]


def _check_response(check) -> CompatibilityCheckResponse:
    return CompatibilityCheckResponse(
        id=check.id,
        scan_result_id=check.scan_result_id,
        printer_id=check.printer_id,
        status=check.status,
        source_type=check.source_type,
        confidence_label=check.confidence_label,
        model_title=check.model_title,
        model_url=check.model_url,
        printer_name=check.printer_name,
        duration_ms=check.duration_ms,
        created_at=check.created_at.isoformat(),
        items=[
            CompatibilityCheckItemResponse(code=item.code, severity=item.severity, message=item.message)
            for item in check.items
        ],
    )
