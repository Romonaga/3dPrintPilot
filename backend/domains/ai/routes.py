from __future__ import annotations

import csv
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import get_db_session
from backend.core.secrets import get_secret_cipher
from backend.domains.ai.schemas.request import ReconcileOpenAICostsRequest, RunAiTaskRequest
from backend.domains.ai.schemas.response import (
    AiAccountingStatusResponse,
    AiTaskRunResponse,
    CostReconciliationResponse,
    CostReconciliationRunResponse,
    AiUsageReportResponse,
)
from backend.domains.ai.service import AiTaskInput, AiTaskRunner, BudgetExceededError, create_openai_cost_reconciliation_service
from backend.domains.ai.store import AiAccountingStore
from backend.domains.settings.store import ProviderSecretStore
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/accounting/status", response_model=AiAccountingStatusResponse)
def accounting_status(
    _user=Depends(require_roles("admin")),
    session: Session = Depends(get_db_session),
) -> AiAccountingStatusResponse:
    settings = get_settings()
    store = AiAccountingStore(session)
    secret_store = ProviderSecretStore(session, get_secret_cipher())
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    estimated_mtd = store.sum_provider_estimated_cost("openai", month_start, now)
    return AiAccountingStatusResponse(
        estimated_cost_supported=True,
        final_cost_supported=True,
        reconciliation_required=True,
        reusable_package="local_ai_accounting",
        openai_api_token_configured=secret_store.get_secret_record("openai", "api_token") is not None,
        openai_account_key_configured=secret_store.get_secret_record("openai", "account_key") is not None,
        openai_fallback_enabled=settings.openai_fallback_enabled,
        local_model=settings.local_llm_default_model,
        openai_fallback_model=settings.openai_fallback_model,
        quality_threshold=settings.ai_quality_threshold,
        monthly_budget_usd=str(settings.openai_monthly_budget_usd),
        single_request_budget_usd=str(settings.openai_single_request_budget_usd),
        estimated_month_to_date_usd=str(estimated_mtd),
        budget_remaining_usd=str(max(settings.openai_monthly_budget_usd - estimated_mtd, Decimal("0"))),
    )


@router.post("/tasks/run", response_model=AiTaskRunResponse)
def run_ai_task(
    request: RunAiTaskRequest,
    user=Depends(require_roles("user")),
    session: Session = Depends(get_db_session),
) -> AiTaskRunResponse:
    settings = get_settings()
    secret_store = ProviderSecretStore(session, get_secret_cipher())
    runner = AiTaskRunner(
        store=AiAccountingStore(session),
        local_model=settings.local_llm_default_model,
        openai_model=settings.openai_fallback_model,
        quality_threshold=settings.ai_quality_threshold,
        openai_fallback_enabled=settings.openai_fallback_enabled,
        openai_api_token_configured=secret_store.get_secret_record("openai", "api_token") is not None,
        monthly_budget_usd=settings.openai_monthly_budget_usd,
        single_request_budget_usd=settings.openai_single_request_budget_usd,
    )
    try:
        result = runner.run(
            AiTaskInput(
                task_type=request.task_type,
                prompt=request.prompt,
                context_type=request.context_type,
                context_id=request.context_id,
                allow_openai_fallback=request.allow_openai_fallback,
                user_id=getattr(user, "id", None),
            )
        )
    except BudgetExceededError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    return AiTaskRunResponse(
        provider=result.provider,
        model_name=result.model_name,
        task_type=result.task_type,
        output_text=result.output_text,
        quality_score=result.quality_score,
        fallback_used=result.fallback_used,
        fallback_reason=result.fallback_reason,
        estimated_cost_usd=str(result.estimated_cost_usd),
        cost_status=result.cost_status,
        usage_event_id=result.usage_event_id,
    )


@router.post("/accounting/reconcile/openai", response_model=CostReconciliationResponse)
def reconcile_openai_costs(
    request: ReconcileOpenAICostsRequest,
    _user=Depends(require_roles("admin")),
    session: Session = Depends(get_db_session),
) -> CostReconciliationResponse:
    secret_store = ProviderSecretStore(session, get_secret_cipher())
    account_key = secret_store.get_secret_value("openai", "account_key")
    if not account_key:
        raise HTTPException(status_code=409, detail="OpenAI account key is not configured")

    service = create_openai_cost_reconciliation_service(
        store=AiAccountingStore(session),
        admin_api_key=account_key,
    )
    try:
        result = service.reconcile_period(period_start=request.period_start, period_end=request.period_end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CostReconciliationResponse(
        run_id=result.run_id,
        status=result.status,
        period_start=result.period_start.isoformat(),
        period_end=result.period_end.isoformat(),
        estimated_total_usd=str(result.estimated_total_usd),
        final_total_usd=str(result.final_total_usd) if result.final_total_usd is not None else None,
        event_count=result.event_count,
        updated_event_count=result.updated_event_count,
        bucket_count=result.bucket_count,
    )


@router.get("/accounting/reconciliation-runs", response_model=list[CostReconciliationRunResponse])
def list_reconciliation_runs(
    _user=Depends(require_roles("admin")),
    session: Session = Depends(get_db_session),
) -> list[CostReconciliationRunResponse]:
    runs = AiAccountingStore(session).list_reconciliation_runs()
    return [
        CostReconciliationRunResponse(
            run_id=run.id,
            status=run.status,
            period_start=run.period_start.isoformat(),
            period_end=run.period_end.isoformat(),
            started_at=run.started_at.isoformat(),
            finished_at=run.finished_at.isoformat() if run.finished_at is not None else None,
            estimated_total_usd=str(run.estimated_total_usd),
            final_total_usd=str(run.final_total_usd) if run.final_total_usd is not None else None,
            details=run.details,
        )
        for run in runs
    ]


@router.get("/accounting/usage-report", response_model=AiUsageReportResponse)
def usage_report(
    _user=Depends(require_roles("admin")),
    session: Session = Depends(get_db_session),
) -> AiUsageReportResponse:
    settings = get_settings()
    start, end = _month_window()
    summary = AiAccountingStore(session).usage_summary(start, end, settings.openai_monthly_budget_usd)
    return AiUsageReportResponse(
        estimated_total_usd=str(summary["estimated_total_usd"]),
        final_total_usd=str(summary["final_total_usd"]) if summary["final_total_usd"] is not None else None,
        event_count=summary["event_count"],
        openai_event_count=summary["openai_event_count"],
        local_event_count=summary["local_event_count"],
        budget_limit_usd=str(summary["budget_limit_usd"]),
        budget_remaining_usd=str(summary["budget_remaining_usd"]),
    )


@router.get("/accounting/usage.csv")
def usage_csv(
    _user=Depends(require_roles("admin")),
    session: Session = Depends(get_db_session),
) -> Response:
    start, end = _month_window()
    events = AiAccountingStore(session).usage_events(start, end)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "created_at",
            "provider",
            "model_name",
            "task_type",
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "estimated_cost_usd",
            "final_cost_usd",
            "cost_status",
            "context_type",
            "context_id",
        ]
    )
    for event in events:
        writer.writerow(
            [
                event.created_at.isoformat(),
                event.provider,
                event.model_name,
                event.task_type,
                event.input_tokens,
                event.cached_input_tokens,
                event.output_tokens,
                event.reasoning_tokens,
                event.estimated_cost_usd,
                event.final_cost_usd or "",
                event.cost_status,
                event.context_type or "",
                event.context_id or "",
            ]
        )
    return Response(buffer.getvalue(), media_type="text/csv")


def _month_window() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC), now
