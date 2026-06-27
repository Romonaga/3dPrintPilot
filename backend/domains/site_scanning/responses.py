from __future__ import annotations

from backend.domains.site_scanning.entities import ScanResult
from backend.domains.site_scanning.schemas.response import (
    SiteAuthBrowserLinkResponse,
    SiteAuthProfileResponse,
    SiteAuthReadinessResponse,
    SiteScanAdapterResponse,
    SiteScanCandidateResponse,
    SiteScanRejectionResponse,
    SiteScanResponse,
    SiteScanSummaryResponse,
)
from backend.domains.site_scanning.runners import SourceSiteCapability, SourceSiteSupportLevel
from backend.domains.site_scanning.store import SiteAuthReadiness, mask_account_identifier, mask_site_auth_secret


def site_scan_adapter_response(record, runner_manifest) -> SiteScanAdapterResponse:
    capabilities = (
        [capability.value for capability in runner_manifest.capabilities]
        if runner_manifest is not None
        else [SourceSiteCapability.PUBLIC_SCAN.value]
    )
    support_level = (
        runner_manifest.support_level.value if runner_manifest is not None else SourceSiteSupportLevel.GENERIC_ONLY.value
    )
    setup_required = runner_manifest.setup_required if runner_manifest is not None else False
    return SiteScanAdapterResponse(
        site_key=record.site_key,
        display_name=record.display_name,
        support_level=support_level,
        capabilities=capabilities,
        setup_required=setup_required,
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


def site_auth_profile_response(declaration, record) -> SiteAuthProfileResponse:
    readiness = readiness_from_profile(declaration.site_key, record)
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


def site_auth_readiness_response(declaration, record, readiness) -> SiteAuthReadinessResponse:
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


def browser_link_response(declaration, status, auth_profile: SiteAuthProfileResponse | None) -> SiteAuthBrowserLinkResponse:
    return SiteAuthBrowserLinkResponse(
        site_key=declaration.site_key,
        display_name=declaration.display_name,
        auth_mode="browser_session",
        session_id=status.session_id,
        status=status.status,
        message=status.message,
        login_url=status.login_url,
        expires_at=status.expires_at.isoformat(),
        cookie_count=status.cookie_count,
        auth_profile=auth_profile,
    )


def readiness_from_profile(site_key: str, record):
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


def site_scan_response(result: ScanResult, scan_run_id: int | None = None) -> SiteScanResponse:
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
