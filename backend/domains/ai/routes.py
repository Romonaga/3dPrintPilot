from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.core.secrets import get_secret_cipher
from backend.domains.ai.schemas.request import ReconcileOpenAICostsRequest
from backend.domains.ai.schemas.response import (
    AiAccountingStatusResponse,
    CostReconciliationResponse,
    CostReconciliationRunResponse,
)
from backend.domains.ai.service import create_openai_cost_reconciliation_service
from backend.domains.ai.store import AiAccountingStore
from backend.domains.settings.store import ProviderSecretStore

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/accounting/status", response_model=AiAccountingStatusResponse)
def accounting_status(session: Session = Depends(get_db_session)) -> AiAccountingStatusResponse:
    secret_store = ProviderSecretStore(session, get_secret_cipher())
    return AiAccountingStatusResponse(
        estimated_cost_supported=True,
        final_cost_supported=True,
        reconciliation_required=True,
        reusable_package="local_ai_accounting",
        openai_api_token_configured=secret_store.get_secret_record("openai", "api_token") is not None,
        openai_account_key_configured=secret_store.get_secret_record("openai", "account_key") is not None,
    )


@router.post("/accounting/reconcile/openai", response_model=CostReconciliationResponse)
def reconcile_openai_costs(
    request: ReconcileOpenAICostsRequest,
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
def list_reconciliation_runs(session: Session = Depends(get_db_session)) -> list[CostReconciliationRunResponse]:
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
