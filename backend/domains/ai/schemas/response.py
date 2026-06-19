from __future__ import annotations

from pydantic import BaseModel


class AiAccountingStatusResponse(BaseModel):
    estimated_cost_supported: bool
    final_cost_supported: bool
    reconciliation_required: bool
    reusable_package: str
    openai_api_token_configured: bool
    openai_account_key_configured: bool
    openai_fallback_enabled: bool
    local_model: str
    openai_fallback_model: str
    quality_threshold: float
    monthly_budget_usd: str
    single_request_budget_usd: str
    estimated_month_to_date_usd: str
    budget_remaining_usd: str


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


class AiTaskRunResponse(BaseModel):
    provider: str
    model_name: str
    task_type: str
    output_text: str
    quality_score: float
    fallback_used: bool
    fallback_reason: str | None
    estimated_cost_usd: str
    cost_status: str
    usage_event_id: int | None


class AiUsageReportResponse(BaseModel):
    estimated_total_usd: str
    final_total_usd: str | None
    event_count: int
    openai_event_count: int
    local_event_count: int
    budget_limit_usd: str
    budget_remaining_usd: str
