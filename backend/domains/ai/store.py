from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domains.ai.models import AiCostReconciliationRun, AiUsageEvent
from local_ai_accounting.models import CostStatus, EventCostUpdate, TokenUsage, UsageCostEvent


class AiAccountingStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_reconcilable_events(self, start: datetime, end: datetime) -> list[UsageCostEvent]:
        statement = (
            select(AiUsageEvent)
            .where(
                AiUsageEvent.provider == "openai",
                AiUsageEvent.created_at >= start,
                AiUsageEvent.created_at < end,
                AiUsageEvent.cost_status.in_([CostStatus.ESTIMATED.value, CostStatus.NEEDS_REVIEW.value]),
            )
            .order_by(AiUsageEvent.created_at, AiUsageEvent.id)
        )
        return [_usage_cost_event(event) for event in self._session.scalars(statement).all()]

    def sum_estimated_cost(self, start: datetime, end: datetime) -> Decimal:
        return sum((event.estimated_cost_usd for event in self.list_reconcilable_events(start, end)), Decimal("0"))

    def create_reconciliation_run(
        self,
        *,
        run_id: str,
        period_start: datetime,
        period_end: datetime,
        estimated_total_usd: Decimal,
        details: dict,
    ) -> AiCostReconciliationRun:
        run = AiCostReconciliationRun(
            id=run_id,
            provider="openai",
            period_start=period_start,
            period_end=period_end,
            status="running",
            estimated_total_usd=estimated_total_usd,
            details=details,
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def complete_reconciliation_run(
        self,
        run_id: str,
        *,
        status: str,
        final_total_usd: Decimal | None,
        details: dict,
    ) -> AiCostReconciliationRun:
        run = self._session.get(AiCostReconciliationRun, run_id)
        if run is None:
            raise ValueError("Reconciliation run not found")
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.final_total_usd = final_total_usd
        run.details = details
        self._session.commit()
        self._session.refresh(run)
        return run

    def apply_event_updates(self, updates: list[EventCostUpdate]) -> None:
        now = datetime.now(UTC)
        for update in updates:
            event = self._session.get(AiUsageEvent, int(update.event_id))
            if event is None:
                continue
            event.final_cost_usd = update.final_cost_usd
            event.cost_status = update.cost_status.value
            event.cost_reconciled_at = now
            event.cost_source = "openai_organization_costs"
            event.cost_discrepancy_usd = update.cost_discrepancy_usd
            event.reconciliation_run_id = update.reconciliation_run_id
            event.raw_usage = {**(event.raw_usage or {}), "cost_allocation_method": update.allocation_method}
        self._session.commit()

    def list_reconciliation_runs(self, limit: int = 20) -> list[AiCostReconciliationRun]:
        statement = select(AiCostReconciliationRun).order_by(AiCostReconciliationRun.started_at.desc()).limit(limit)
        return list(self._session.scalars(statement).all())


def _usage_cost_event(event: AiUsageEvent) -> UsageCostEvent:
    return UsageCostEvent(
        event_id=str(event.id),
        created_at=event.created_at,
        provider=event.provider,
        model_name=event.model_name,
        usage=TokenUsage(
            input_tokens=event.input_tokens,
            cached_input_tokens=event.cached_input_tokens,
            output_tokens=event.output_tokens,
            reasoning_tokens=event.reasoning_tokens,
            total_tokens=event.input_tokens + event.output_tokens,
        ),
        estimated_cost_usd=Decimal(event.estimated_cost_usd),
        final_cost_usd=Decimal(event.final_cost_usd) if event.final_cost_usd is not None else None,
        cost_status=CostStatus(event.cost_status),
    )
