from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
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

    def sum_provider_estimated_cost(self, provider: str, start: datetime, end: datetime) -> Decimal:
        statement = select(func.coalesce(func.sum(AiUsageEvent.estimated_cost_usd), 0)).where(
            AiUsageEvent.provider == provider,
            AiUsageEvent.created_at >= start,
            AiUsageEvent.created_at < end,
        )
        return Decimal(str(self._session.execute(statement).scalar_one() or "0"))

    def record_usage_event(
        self,
        *,
        provider: str,
        model_name: str,
        task_type: str,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: Decimal,
        cost_status: str,
        user_id: int | None = None,
        context_type: str | None = None,
        context_id: str | None = None,
        cached_input_tokens: int = 0,
        reasoning_tokens: int = 0,
        latency_ms: int | None = None,
        success: bool = True,
        error_message: str | None = None,
        raw_usage: dict | None = None,
    ) -> AiUsageEvent:
        event = AiUsageEvent(
            user_id=user_id,
            provider=provider,
            model_name=model_name,
            task_type=task_type,
            context_type=context_type,
            context_id=context_id,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            estimated_cost_usd=estimated_cost_usd,
            cost_status=cost_status,
            cost_source="local_estimate",
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
            raw_usage=raw_usage or {},
        )
        self._session.add(event)
        self._session.commit()
        self._session.refresh(event)
        return event

    def usage_events(self, start: datetime, end: datetime) -> list[AiUsageEvent]:
        statement = (
            select(AiUsageEvent)
            .where(AiUsageEvent.created_at >= start, AiUsageEvent.created_at < end)
            .order_by(AiUsageEvent.created_at.desc(), AiUsageEvent.id.desc())
        )
        return list(self._session.scalars(statement).all())

    def usage_summary(self, start: datetime, end: datetime, budget_limit_usd: Decimal) -> dict:
        events = self.usage_events(start, end)
        estimated_total = sum((Decimal(event.estimated_cost_usd) for event in events), Decimal("0"))
        final_values = [Decimal(event.final_cost_usd) for event in events if event.final_cost_usd is not None]
        return {
            "estimated_total_usd": estimated_total,
            "final_total_usd": sum(final_values, Decimal("0")) if final_values else None,
            "event_count": len(events),
            "openai_event_count": sum(1 for event in events if event.provider == "openai"),
            "local_event_count": sum(1 for event in events if event.provider == "ollama"),
            "budget_limit_usd": budget_limit_usd,
            "budget_remaining_usd": max(Decimal("0"), budget_limit_usd - estimated_total),
        }

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
