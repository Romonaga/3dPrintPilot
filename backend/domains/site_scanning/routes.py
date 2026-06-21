from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.core.secrets import get_secret_cipher
from backend.domains.site_scanning.entities import CrawlPolicy, ScanResult
from backend.domains.site_scanning.schemas.request import SiteScanRequest, UpdateSiteAdapterRequest, UpsertSiteAuthProfileRequest
from backend.domains.site_scanning.schemas.response import (
    SiteAuthLinkResponse,
    SiteAuthProfileResponse,
    SiteAuthReadinessResponse,
    SiteScanAdapterResponse,
    SiteScanCandidateResponse,
    SiteScanRejectionResponse,
    SiteScanResponse,
    SiteScanSummaryResponse,
)
from backend.domains.site_scanning.service import SiteScanService
from backend.domains.site_scanning.store import (
    SiteAuthProfileStore,
    SiteAuthReadiness,
    SiteScanStore,
    mask_account_identifier,
    mask_site_auth_secret,
)
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/site-scanning", tags=["site-scanning"])
service = SiteScanService()


def get_site_scan_store(session: Session = Depends(get_db_session)) -> SiteScanStore:
    return SiteScanStore(session)


def get_site_auth_profile_store(session: Session = Depends(get_db_session)) -> SiteAuthProfileStore:
    return SiteAuthProfileStore(session, get_secret_cipher())


@router.get("/adapters", response_model=list[SiteScanAdapterResponse])
def list_adapters(
    _user=Depends(require_roles("viewer")),
    store: SiteScanStore = Depends(get_site_scan_store),
) -> list[SiteScanAdapterResponse]:
    return [
        SiteScanAdapterResponse(
            site_key=record.site_key,
            display_name=record.display_name,
            base_url=record.base_url,
            login_url=record.login_url,
            enabled=record.enabled,
            supports_downloads=record.supports_downloads,
            supported_auth_modes=list((record.auth_capabilities or {}).get("supported_auth_modes") or ["none"]),
            auth_storage_notes=(record.auth_capabilities or {}).get("auth_storage_notes"),
            allowed_hosts=list((record.allowed_hosts or {}).get("hosts") or []),
            default_limits=record.default_limits or {},
            robots_terms_notes=record.robots_terms_notes,
        )
        for record in store.list_adapter_records(service.adapter_declarations())
    ]


@router.put("/adapters/{site_key}", response_model=SiteScanAdapterResponse)
def update_adapter(
    site_key: str,
    request: UpdateSiteAdapterRequest,
    _user=Depends(require_roles("admin")),
    store: SiteScanStore = Depends(get_site_scan_store),
) -> SiteScanAdapterResponse:
    record = store.update_adapter_enabled(service.adapter_declarations(), site_key, request.enabled)
    if record is None:
        raise HTTPException(status_code=404, detail="Site adapter not found")
    return SiteScanAdapterResponse(
        site_key=record.site_key,
        display_name=record.display_name,
        base_url=record.base_url,
        login_url=record.login_url,
        enabled=record.enabled,
        supports_downloads=record.supports_downloads,
        supported_auth_modes=list((record.auth_capabilities or {}).get("supported_auth_modes") or ["none"]),
        auth_storage_notes=(record.auth_capabilities or {}).get("auth_storage_notes"),
        allowed_hosts=list((record.allowed_hosts or {}).get("hosts") or []),
        default_limits=record.default_limits or {},
        robots_terms_notes=record.robots_terms_notes,
    )


@router.get("/auth-profiles", response_model=list[SiteAuthProfileResponse])
def list_site_auth_profiles(
    _user=Depends(require_roles("admin")),
    store: SiteAuthProfileStore = Depends(get_site_auth_profile_store),
) -> list[SiteAuthProfileResponse]:
    return [
        _site_auth_profile_response(declaration, record)
        for declaration, record in store.list_profile_statuses(service.adapter_declarations())
    ]


@router.put("/auth-profiles/{site_key}", response_model=SiteAuthProfileResponse)
def upsert_site_auth_profile(
    site_key: str,
    request: UpsertSiteAuthProfileRequest,
    _user=Depends(require_roles("admin")),
    store: SiteAuthProfileStore = Depends(get_site_auth_profile_store),
) -> SiteAuthProfileResponse:
    declarations = service.adapter_declarations()
    try:
        record = store.upsert_profile(
            declarations,
            site_key=site_key,
            auth_mode=request.auth_mode,
            secret_value=request.secret_value,
            label=request.label,
            account_identifier=request.account_identifier,
            header_name=request.header_name,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    declaration = next(declaration for declaration in declarations if declaration.site_key == record.site_key)
    return _site_auth_profile_response(declaration, record)


@router.get("/auth-profiles/{site_key}/link", response_model=SiteAuthLinkResponse)
def start_site_auth_link(
    site_key: str,
    _user=Depends(require_roles("admin")),
) -> SiteAuthLinkResponse:
    declaration = _find_declaration(site_key)
    if "browser_session" not in declaration.supported_auth_modes:
        raise HTTPException(status_code=400, detail="Site does not support browser-assisted linking")
    return SiteAuthLinkResponse(
        site_key=declaration.site_key,
        display_name=declaration.display_name,
        auth_mode="browser_session",
        login_url=declaration.login_url,
        account_identifier=None,
        instructions=[
            "Open the site login page and complete sign-in with the provider account.",
            "Copy only the site-scoped session cookie or Cookie header after sign-in.",
            "Paste the Printables session value back into this app to store it encrypted.",
        ],
        storage_notes=(
            "This flow never asks for a Google password and does not read the normal browser cookie store. "
            "Only the Printables session value you explicitly paste is encrypted for later unattended use."
        ),
    )


@router.post("/auth-profiles/{site_key}/test", response_model=SiteAuthReadinessResponse)
def test_site_auth_profile(
    site_key: str,
    _user=Depends(require_roles("admin")),
    store: SiteAuthProfileStore = Depends(get_site_auth_profile_store),
) -> SiteAuthReadinessResponse:
    declaration = _find_declaration(site_key)
    try:
        readiness = store.readiness_for_site(service.adapter_declarations(), site_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record = store.get_profile(readiness.site_key)
    return _site_auth_readiness_response(declaration, record, readiness)


@router.delete("/auth-profiles/{site_key}", status_code=204)
def delete_site_auth_profile(
    site_key: str,
    _user=Depends(require_roles("admin")),
    store: SiteAuthProfileStore = Depends(get_site_auth_profile_store),
) -> Response:
    if not store.delete_profile(site_key):
        raise HTTPException(status_code=404, detail="Site auth profile not found")
    return Response(status_code=204)


@router.post("/scans", response_model=SiteScanResponse)
def create_scan(
    request: SiteScanRequest,
    user=Depends(require_roles("user")),
    store: SiteScanStore = Depends(get_site_scan_store),
    auth_store: SiteAuthProfileStore = Depends(get_site_auth_profile_store),
) -> SiteScanResponse:
    declarations = service.adapter_declarations()
    auth_headers_by_site = _auth_headers_by_site(auth_store, declarations)
    try:
        result = service.scan(
            start_url=request.url,
            site_key=request.site_key,
            policy=CrawlPolicy(
                max_depth=request.max_depth,
                max_pages=request.max_pages,
                max_runtime_seconds=request.max_runtime_seconds,
                same_domain_only=request.same_domain_only,
                allowed_hosts=frozenset(request.allowed_hosts),
                per_host_concurrency=request.per_host_concurrency,
            ),
            enabled_site_keys=store.enabled_site_keys(declarations),
            auth_headers_by_site=auth_headers_by_site,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    scan_run = store.save_scan_result(result, requested_by_user_id=getattr(user, "id", None))
    return _to_response(result, scan_run_id=scan_run.id)


def _site_auth_profile_response(declaration, record) -> SiteAuthProfileResponse:
    readiness = _readiness_from_profile(declaration.site_key, record)
    return SiteAuthProfileResponse(
        site_key=declaration.site_key,
        display_name=declaration.display_name,
        auth_mode=record.auth_mode if record is not None else "none",
        label=record.label if record is not None else None,
        account_identifier=record.account_identifier if record is not None else None,
        masked_account_identifier=mask_account_identifier(record.account_identifier if record is not None else None),
        header_name=record.header_name if record is not None else None,
        configured=record is not None and record.encrypted_value is not None,
        enabled=record.enabled if record is not None else False,
        auth_ready=readiness.auth_ready,
        link_status=readiness.link_status,
        link_status_message=readiness.message,
        masked_value=mask_site_auth_secret(record),
        updated_at=record.updated_at.isoformat() if record is not None and record.updated_at is not None else None,
    )


def _site_auth_readiness_response(declaration, record, readiness) -> SiteAuthReadinessResponse:
    return SiteAuthReadinessResponse(
        site_key=declaration.site_key,
        display_name=declaration.display_name,
        auth_mode=readiness.auth_mode,
        auth_ready=readiness.auth_ready,
        link_status=readiness.link_status,
        message=readiness.message,
        configured=readiness.configured,
        enabled=readiness.enabled,
        masked_account_identifier=mask_account_identifier(record.account_identifier if record is not None else None),
        masked_value=mask_site_auth_secret(record),
        updated_at=record.updated_at.isoformat() if record is not None and record.updated_at is not None else None,
    )


def _readiness_from_profile(site_key: str, record):
    if record is None or record.auth_mode == "none":
        return SiteAuthReadiness(
            site_key=site_key,
            auth_mode="none",
            auth_ready=False,
            link_status="public_only",
            message="Public scans can run without an account. Link an account for authenticated access.",
            configured=False,
            enabled=False,
        )
    if not record.enabled:
        return SiteAuthReadiness(
            site_key=site_key,
            auth_mode=record.auth_mode,
            auth_ready=False,
            link_status="disabled",
            message="Account link is saved but disabled.",
            configured=record.encrypted_value is not None,
            enabled=False,
        )
    if record.encrypted_value is None:
        return SiteAuthReadiness(
            site_key=site_key,
            auth_mode=record.auth_mode,
            auth_ready=False,
            link_status="needs_relink" if record.auth_mode == "browser_session" else "not_linked",
            message="Browser session is not stored yet. Complete browser login and save a Printables session value.",
            configured=False,
            enabled=True,
        )
    return SiteAuthReadiness(
        site_key=site_key,
        auth_mode=record.auth_mode,
        auth_ready=True,
        link_status="linked",
        message="Stored account link is available for unattended authenticated requests.",
        configured=True,
        enabled=True,
    )


def _find_declaration(site_key: str):
    normalized_site_key = site_key.strip().lower()
    declaration = next(
        (declaration for declaration in service.adapter_declarations() if declaration.site_key == normalized_site_key),
        None,
    )
    if declaration is None:
        raise HTTPException(status_code=404, detail="Site adapter not found")
    return declaration


def _auth_headers_by_site(auth_store: SiteAuthProfileStore, declarations) -> dict[str, dict[str, str]]:
    headers_by_site: dict[str, dict[str, str]] = {}
    for declaration in declarations:
        context = auth_store.auth_context_for_site(declaration.site_key)
        if context.enabled and context.headers:
            headers_by_site[declaration.site_key] = context.headers
    return headers_by_site


def _to_response(result: ScanResult, scan_run_id: int | None = None) -> SiteScanResponse:
    summary = result.summary
    return SiteScanResponse(
        summary=SiteScanSummaryResponse(
            scan_run_id=scan_run_id,
            status=summary.status.value,
            stop_reason=summary.stop_reason.value,
            start_url=summary.start_url,
            normalized_start_url=summary.normalized_start_url,
            site_key=summary.site_key,
            max_depth=summary.max_depth,
            max_pages=summary.max_pages,
            max_runtime_seconds=summary.max_runtime_seconds,
            same_domain_only=summary.same_domain_only,
            per_host_concurrency=summary.per_host_concurrency,
            queued_url_count=summary.queued_url_count,
            scanned_url_count=summary.scanned_url_count,
            accepted_result_count=summary.accepted_result_count,
            rejected_url_count=summary.rejected_url_count,
            duration_ms=summary.duration_ms,
        ),
        candidates=[
            SiteScanCandidateResponse(
                source_url=candidate.source_url,
                title=candidate.title,
                depth=candidate.depth,
                parent_url=candidate.parent_url,
                normalized_url=candidate.normalized_url,
                inclusion_reason=candidate.inclusion_reason,
                status=candidate.status,
                confidence=candidate.confidence,
                evidence=list(candidate.evidence),
                license=candidate.license,
                attribution=candidate.attribution,
                requirements=candidate.requirements,
            )
            for candidate in result.candidates
        ],
        rejections=[
            SiteScanRejectionResponse(
                source_url=rejection.source_url,
                reason=rejection.reason,
                depth=rejection.depth,
                parent_url=rejection.parent_url,
            )
            for rejection in result.rejections
        ],
    )
