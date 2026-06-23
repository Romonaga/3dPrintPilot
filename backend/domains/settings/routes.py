from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import get_db_session
from backend.core.secrets import get_secret_cipher
from backend.domains.settings.schemas.request import UpdateAuthSettingsRequest, UpsertProviderSecretRequest
from backend.domains.settings.schemas.response import AuthSettingsResponse, FeatureSettingsResponse, ProviderSecretStatusResponse
from backend.domains.settings.store import (
    InstanceSettingsStore,
    MAX_SESSION_TIMEOUT_MINUTES,
    MIN_SESSION_TIMEOUT_MINUTES,
    ProviderSecretStore,
    mask_secret,
)
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/settings", tags=["settings"])


def get_provider_secret_store(session: Session = Depends(get_db_session)) -> ProviderSecretStore:
    return ProviderSecretStore(session, get_secret_cipher())


def get_instance_settings_store(session: Session = Depends(get_db_session)) -> InstanceSettingsStore:
    return InstanceSettingsStore(session)


@router.get("/features", response_model=FeatureSettingsResponse)
def feature_settings() -> FeatureSettingsResponse:
    settings = get_settings()
    return FeatureSettingsResponse(
        openai_fallback_enabled=settings.openai_fallback_enabled,
        openai_fallback_model=settings.openai_fallback_model,
        ai_quality_threshold=settings.ai_quality_threshold,
        openai_monthly_budget_usd=str(settings.openai_monthly_budget_usd),
        openai_single_request_budget_usd=str(settings.openai_single_request_budget_usd),
        cost_reconciliation_required=True,
        local_ai_provider="ollama",
        local_ai_default_model=settings.local_llm_default_model,
    )


@router.get("/auth", response_model=AuthSettingsResponse)
def auth_settings(
    _user=Depends(require_roles("admin")),
    store: InstanceSettingsStore = Depends(get_instance_settings_store),
) -> AuthSettingsResponse:
    settings = store.get_auth_settings()
    return _auth_settings_response(settings)


@router.put("/auth", response_model=AuthSettingsResponse)
def update_auth_settings(
    request: UpdateAuthSettingsRequest,
    _user=Depends(require_roles("admin")),
    store: InstanceSettingsStore = Depends(get_instance_settings_store),
) -> AuthSettingsResponse:
    try:
        settings = store.update_auth_settings(request.session_timeout_minutes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _auth_settings_response(settings)


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


def _auth_settings_response(settings) -> AuthSettingsResponse:
    return AuthSettingsResponse(
        session_timeout_minutes=settings.session_timeout_minutes,
        min_session_timeout_minutes=MIN_SESSION_TIMEOUT_MINUTES,
        max_session_timeout_minutes=MAX_SESSION_TIMEOUT_MINUTES,
    )
