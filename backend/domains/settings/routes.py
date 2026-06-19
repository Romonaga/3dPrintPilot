from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import get_db_session
from backend.core.secrets import get_secret_cipher
from backend.domains.settings.schemas.request import UpsertProviderSecretRequest
from backend.domains.settings.schemas.response import FeatureSettingsResponse, ProviderSecretStatusResponse
from backend.domains.settings.store import ProviderSecretStore, mask_secret
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/settings", tags=["settings"])


def get_provider_secret_store(session: Session = Depends(get_db_session)) -> ProviderSecretStore:
    return ProviderSecretStore(session, get_secret_cipher())


@router.get("/features", response_model=FeatureSettingsResponse)
def feature_settings() -> FeatureSettingsResponse:
    settings = get_settings()
    return FeatureSettingsResponse(
        openai_fallback_enabled=settings.openai_fallback_enabled,
        cost_reconciliation_required=True,
        local_ai_provider="ollama",
        local_ai_default_model=settings.local_llm_default_model,
    )


@router.get("/provider-secrets", response_model=list[ProviderSecretStatusResponse])
def list_provider_secrets(
    _user=Depends(require_roles("admin")),
    store: ProviderSecretStore = Depends(get_provider_secret_store),
) -> list[ProviderSecretStatusResponse]:
    return [_secret_status_response(known, record) for known, record in store.list_secret_statuses()]


@router.put("/provider-secrets/{provider}/{secret_name}", response_model=ProviderSecretStatusResponse)
def upsert_provider_secret(
    provider: str,
    secret_name: str,
    request: UpsertProviderSecretRequest,
    _user=Depends(require_roles("admin")),
    store: ProviderSecretStore = Depends(get_provider_secret_store),
) -> ProviderSecretStatusResponse:
    try:
        record = store.upsert_secret(provider, secret_name, request.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    known = next(
        known
        for known, candidate in store.list_secret_statuses()
        if known.provider == record.provider and known.secret_name == record.secret_name
    )
    return _secret_status_response(known, record)


@router.delete("/provider-secrets/{provider}/{secret_name}", status_code=204)
def delete_provider_secret(
    provider: str,
    secret_name: str,
    _user=Depends(require_roles("admin")),
    store: ProviderSecretStore = Depends(get_provider_secret_store),
) -> Response:
    if not store.delete_secret(provider, secret_name):
        raise HTTPException(status_code=404, detail="Provider secret not found")
    return Response(status_code=204)


def _secret_status_response(known, record) -> ProviderSecretStatusResponse:
    return ProviderSecretStatusResponse(
        provider=known.provider,
        secret_name=known.secret_name,
        label=known.label,
        purpose=known.purpose,
        configured=record is not None,
        masked_value=mask_secret(record),
        updated_at=record.updated_at.isoformat() if record is not None else None,
    )
