from __future__ import annotations

from pydantic import BaseModel


class AiAccountingStatusResponse(BaseModel):
    estimated_cost_supported: bool
    final_cost_supported: bool
    reconciliation_required: bool
    reusable_package: str
    openai_api_token_configured: bool
    openai_account_key_configured: bool


class CostReconciliationResponse(BaseModel):
    run_id: str
    status: str
    period_start: str
    period_end: str
    estimated_total_usd: str
    final_total_usd: str | None
    event_count: int
    updated_event_count: int
    bucket_count: int


class CostReconciliationRunResponse(BaseModel):
    run_id: str
    status: str
    period_start: str
    period_end: str
    started_at: str
    finished_at: str | None
    estimated_total_usd: str
    final_total_usd: str | None
    details: dict
