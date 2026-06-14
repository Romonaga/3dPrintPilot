from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class CostStatus(StrEnum):
    ESTIMATED = "estimated"
    VERIFIED = "verified"
    ADJUSTED = "adjusted"
    NEEDS_REVIEW = "needs_review"
    NOT_BILLABLE = "not_billable"


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class OpenAIPricingRate:
    model_name: str
    input_per_1m_tokens: Decimal
    cached_input_per_1m_tokens: Decimal
    output_per_1m_tokens: Decimal
    currency: str = "USD"


@dataclass(frozen=True)
class UsageCostEvent:
    event_id: str
    created_at: datetime
    provider: str
    model_name: str
    usage: TokenUsage
    estimated_cost_usd: Decimal
    final_cost_usd: Decimal | None = None
    cost_status: CostStatus = CostStatus.ESTIMATED


@dataclass(frozen=True)
class EventCostUpdate:
    event_id: str
    estimated_cost_usd: Decimal
    final_cost_usd: Decimal
    cost_status: CostStatus
    cost_discrepancy_usd: Decimal
    reconciliation_run_id: str
    allocation_method: str

