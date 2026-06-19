from __future__ import annotations

from pydantic import BaseModel


class FeatureSettingsResponse(BaseModel):
    openai_fallback_enabled: bool
    openai_fallback_model: str
    ai_quality_threshold: float
    openai_monthly_budget_usd: str
    openai_single_request_budget_usd: str
    cost_reconciliation_required: bool
    local_ai_provider: str
    local_ai_default_model: str


class ProviderSecretStatusResponse(BaseModel):
    provider: str
    secret_name: str
    label: str
    purpose: str
    configured: bool
    masked_value: str | None
    updated_at: str | None
