from __future__ import annotations

from pydantic import BaseModel


class CompatibilityCheckItemResponse(BaseModel):
    code: str
    severity: str
    message: str


class CompatibilityCheckResponse(BaseModel):
    id: int
    scan_result_id: int
    printer_id: int
    status: str
    source_type: str
    confidence_label: str
    model_title: str
    model_url: str
    printer_name: str
    duration_ms: int
    created_at: str
    items: list[CompatibilityCheckItemResponse]


class CompatibilityRunResponse(BaseModel):
    scan_run_id: int
    printer_count: int
    candidate_count: int
    check_count: int
    checks: list[CompatibilityCheckResponse]
