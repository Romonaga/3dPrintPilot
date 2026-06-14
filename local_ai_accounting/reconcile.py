from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from local_ai_accounting.estimate import MONEY_QUANT
from local_ai_accounting.models import CostStatus, EventCostUpdate, UsageCostEvent


def reconcile_cost_bucket(
    events: list[UsageCostEvent],
    *,
    verified_cost_usd: Decimal,
    tolerance_usd: Decimal = Decimal("0.000001"),
    reconciliation_run_id: str | None = None,
    allocation_method: str = "estimated_cost_proportional",
) -> list[EventCostUpdate]:
    billable_events = [event for event in events if event.provider == "openai"]
    if not billable_events:
        return []

    run_id = reconciliation_run_id or str(uuid4())
    estimated_total = sum((event.estimated_cost_usd for event in billable_events), Decimal("0"))
    verified = Decimal(str(verified_cost_usd)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    total_discrepancy = (verified - estimated_total).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    bucket_status = CostStatus.VERIFIED if abs(total_discrepancy) <= tolerance_usd else CostStatus.ADJUSTED

    allocated = _allocate_verified_costs(billable_events, verified)
    updates: list[EventCostUpdate] = []
    for event, final_cost in zip(billable_events, allocated, strict=True):
        discrepancy = (final_cost - event.estimated_cost_usd).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        updates.append(
            EventCostUpdate(
                event_id=event.event_id,
                estimated_cost_usd=event.estimated_cost_usd,
                final_cost_usd=final_cost,
                cost_status=bucket_status,
                cost_discrepancy_usd=discrepancy,
                reconciliation_run_id=run_id,
                allocation_method=allocation_method,
            )
        )
    return updates


def _allocate_verified_costs(events: list[UsageCostEvent], verified_cost_usd: Decimal) -> list[Decimal]:
    if len(events) == 1:
        return [verified_cost_usd.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)]

    estimated_total = sum((event.estimated_cost_usd for event in events), Decimal("0"))
    if estimated_total <= 0:
        weights = [Decimal(1) / Decimal(len(events)) for _ in events]
    else:
        weights = [event.estimated_cost_usd / estimated_total for event in events]

    allocated: list[Decimal] = []
    remaining = verified_cost_usd
    for index, weight in enumerate(weights):
        if index == len(weights) - 1:
            final_cost = remaining
        else:
            final_cost = (verified_cost_usd * weight).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            remaining -= final_cost
        allocated.append(final_cost.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))
    return allocated

