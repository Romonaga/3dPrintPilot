from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.secrets import SecretCipher
from backend.domains.site_scanning.adapters.base import SiteAdapterDeclaration
from backend.domains.site_scanning.entities import ScanResult
from backend.domains.site_scanning.models import ModelSiteAdapter, ModelSiteScanResult, ModelSiteScanRun, SiteAuthProfile

SITE_AUTH_MODES = frozenset({"none", "api_token", "bearer_token", "cookie_header", "username_password", "browser_session"})
REQUIRED_SECRET_AUTH_MODES = frozenset({"api_token", "bearer_token", "cookie_header", "username_password"})
OPTIONAL_SECRET_AUTH_MODES = frozenset({"browser_session"})
HEADER_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,119}$")


@dataclass(frozen=True)
class SiteAuthContext:
    site_key: str
    auth_mode: str
    enabled: bool
    headers: dict[str, str]
    account_identifier: str | None = None
    username: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class SiteAuthReadiness:
    site_key: str
    auth_mode: str
    auth_ready: bool
    link_status: str
    message: str
    configured: bool
    enabled: bool


class SiteScanStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_adapter_records(self, declarations: list[SiteAdapterDeclaration]) -> list[ModelSiteAdapter]:
        configured = {adapter.site_key: adapter for adapter in self._session.scalars(select(ModelSiteAdapter)).all()}
        changed = False
        for declaration in declarations:
            if declaration.site_key in configured:
                continue
            record = ModelSiteAdapter(
                site_key=declaration.site_key,
                display_name=declaration.display_name,
                enabled=declaration.enabled,
                supports_downloads=declaration.supports_downloads,
                base_url=declaration.base_url,
                login_url=declaration.login_url,
                auth_capabilities=_auth_capabilities_from_declaration(declaration),
                allowed_hosts={"hosts": list(declaration.allowed_hosts)},
                default_limits=declaration.default_limits,
                robots_terms_notes=declaration.robots_terms_notes,
            )
            self._session.add(record)
            configured[declaration.site_key] = record
            changed = True
        for declaration in declarations:
            record = configured[declaration.site_key]
            next_capabilities = _auth_capabilities_from_declaration(declaration)
            if (
                record.base_url != declaration.base_url
                or record.login_url != declaration.login_url
                or record.auth_capabilities != next_capabilities
            ):
                record.base_url = declaration.base_url
                record.login_url = declaration.login_url
                record.auth_capabilities = next_capabilities
                changed = True
        if changed:
            self._session.commit()
        return [configured[declaration.site_key] for declaration in declarations]

    def enabled_site_keys(self, declarations: list[SiteAdapterDeclaration]) -> frozenset[str]:
        return frozenset(
            record.site_key
            for record in self.list_adapter_records(declarations)
            if record.enabled
        )

    def update_adapter_enabled(
        self,
        declarations: list[SiteAdapterDeclaration],
        site_key: str,
        enabled: bool,
    ) -> ModelSiteAdapter | None:
        records = {record.site_key: record for record in self.list_adapter_records(declarations)}
        record = records.get(site_key)
        if record is None:
            return None
        record.enabled = enabled
        self._session.commit()
        self._session.refresh(record)
        return record

    def save_scan_result(self, result: ScanResult, requested_by_user_id: int | None = None) -> ModelSiteScanRun:
        summary = result.summary
        finished_at = datetime.now(UTC)
        started_at = finished_at
        if summary.duration_ms:
            started_at = datetime.fromtimestamp(finished_at.timestamp() - (summary.duration_ms / 1000), tz=UTC)

        run = ModelSiteScanRun(
            requested_by_user_id=requested_by_user_id,
            site_key=summary.site_key,
            start_url=summary.start_url,
            normalized_start_url=summary.normalized_start_url,
            status=summary.status.value,
            stop_reason=summary.stop_reason.value,
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
            started_at=started_at,
            finished_at=finished_at,
            limits_snapshot={
                "max_depth": summary.max_depth,
                "max_pages": summary.max_pages,
                "max_runtime_seconds": summary.max_runtime_seconds,
                "same_domain_only": summary.same_domain_only,
                "per_host_concurrency": summary.per_host_concurrency,
            },
            raw_summary={
                "queued_url_count": summary.queued_url_count,
                "scanned_url_count": summary.scanned_url_count,
                "accepted_result_count": summary.accepted_result_count,
                "rejected_url_count": summary.rejected_url_count,
            },
        )
        self._session.add(run)
        self._session.flush()

        for candidate in result.candidates:
            self._session.add(
                ModelSiteScanResult(
                    scan_run_id=run.id,
                    site_key=summary.site_key,
                    external_model_id=candidate.external_model_id,
                    source_url=candidate.source_url,
                    normalized_url=candidate.normalized_url,
                    title=candidate.title,
                    depth=candidate.depth,
                    parent_url=candidate.parent_url,
                    result_type="candidate",
                    status=candidate.status,
                    confidence=candidate.confidence,
                    inclusion_reason=candidate.inclusion_reason,
                    evidence={
                        "items": list(candidate.evidence),
                        "license": candidate.license,
                        "attribution": candidate.attribution,
                        "requirements": candidate.requirements,
                    },
                    raw_payload=candidate.raw_payload,
                )
            )

        for rejection in result.rejections:
            self._session.add(
                ModelSiteScanResult(
                    scan_run_id=run.id,
                    site_key=summary.site_key,
                    source_url=rejection.source_url,
                    normalized_url=rejection.source_url,
                    depth=rejection.depth,
                    parent_url=rejection.parent_url,
                    result_type="rejection",
                    status="rejected",
                    rejection_reason=rejection.reason,
                    evidence={"reason": rejection.reason},
                )
            )

        self._session.commit()
        self._session.refresh(run)
        return run


class SiteAuthProfileStore:
    def __init__(self, session: Session, cipher: SecretCipher) -> None:
        self._session = session
        self._cipher = cipher

    def list_profile_statuses(self, declarations: list[SiteAdapterDeclaration]) -> list[tuple[SiteAdapterDeclaration, SiteAuthProfile | None]]:
        configured = {
            profile.site_key: profile
            for profile in self._session.scalars(select(SiteAuthProfile)).all()
        }
        return [(declaration, configured.get(declaration.site_key)) for declaration in declarations]

    def upsert_profile(
        self,
        declarations: list[SiteAdapterDeclaration],
        *,
        site_key: str,
        auth_mode: str,
        secret_value: str | None,
        label: str | None = None,
        account_identifier: str | None = None,
        header_name: str | None = None,
        enabled: bool = True,
    ) -> SiteAuthProfile:
        normalized_site_key = _require_known_site_key(declarations, site_key)
        clean_mode = _normalize_auth_mode(auth_mode)
        clean_label = (label or "").strip()[:160] or None
        clean_account_identifier = _normalize_account_identifier(clean_mode, account_identifier)
        clean_header = _normalize_header_name(clean_mode, header_name)
        clean_secret = _normalize_secret_value(clean_mode, secret_value)
        now = datetime.now(UTC)

        existing = self.get_profile(normalized_site_key)
        if existing is None:
            existing = SiteAuthProfile(
                site_key=normalized_site_key,
                auth_mode=clean_mode,
                label=clean_label,
                account_identifier=clean_account_identifier,
                header_name=clean_header,
                enabled=enabled,
                updated_at=now,
            )
            self._session.add(existing)
        else:
            existing.auth_mode = clean_mode
            existing.label = clean_label
            existing.account_identifier = clean_account_identifier
            existing.header_name = clean_header
            existing.enabled = enabled
            existing.updated_at = now

        if clean_secret is None:
            existing.encrypted_value = None
            existing.encryption_key_id = None
            existing.secret_fingerprint = None
            existing.last_four = None
        else:
            existing.encrypted_value = self._cipher.encrypt(clean_secret)
            existing.encryption_key_id = self._cipher.key_id
            existing.secret_fingerprint = self._cipher.fingerprint(clean_secret)
            existing.last_four = clean_secret[-4:]

        self._session.commit()
        self._session.refresh(existing)
        return existing

    def get_profile(self, site_key: str) -> SiteAuthProfile | None:
        statement = select(SiteAuthProfile).where(SiteAuthProfile.site_key == site_key.strip().lower())
        return self._session.scalars(statement).one_or_none()

    def delete_profile(self, site_key: str) -> bool:
        profile = self.get_profile(site_key)
        if profile is None:
            return False
        self._session.delete(profile)
        self._session.commit()
        return True

    def readiness_for_site(self, declarations: list[SiteAdapterDeclaration], site_key: str) -> SiteAuthReadiness:
        normalized_site_key = _require_known_site_key(declarations, site_key)
        profile = self.get_profile(normalized_site_key)
        if profile is None or profile.auth_mode == "none":
            return SiteAuthReadiness(
                site_key=normalized_site_key,
                auth_mode="none",
                auth_ready=False,
                link_status="public_only",
                message="Public scans can run without an account. Link an account for authenticated access.",
                configured=False,
                enabled=False,
            )
        if not profile.enabled:
            return SiteAuthReadiness(
                site_key=normalized_site_key,
                auth_mode=profile.auth_mode,
                auth_ready=False,
                link_status="disabled",
                message="Account link is saved but disabled.",
                configured=profile.encrypted_value is not None,
                enabled=False,
            )
        if profile.encrypted_value is None:
            status = "needs_relink" if profile.auth_mode == "browser_session" else "not_linked"
            return SiteAuthReadiness(
                site_key=normalized_site_key,
                auth_mode=profile.auth_mode,
                auth_ready=False,
                link_status=status,
                message="Browser session is not stored yet. Complete browser login and save a Printables session value.",
                configured=False,
                enabled=True,
            )
        return SiteAuthReadiness(
            site_key=normalized_site_key,
            auth_mode=profile.auth_mode,
            auth_ready=True,
            link_status="linked",
            message="Stored account link is available for unattended authenticated requests.",
            configured=True,
            enabled=True,
        )

    def auth_context_for_site(self, site_key: str) -> SiteAuthContext:
        normalized_site_key = site_key.strip().lower()
        profile = self.get_profile(normalized_site_key)
        if profile is None or not profile.enabled or profile.auth_mode == "none":
            return SiteAuthContext(site_key=normalized_site_key, auth_mode="none", enabled=False, headers={})
        if profile.encrypted_value is None:
            return SiteAuthContext(site_key=normalized_site_key, auth_mode=profile.auth_mode, enabled=False, headers={})

        secret_value = self._cipher.decrypt(profile.encrypted_value)
        if profile.auth_mode == "api_token" and profile.header_name:
            return SiteAuthContext(
                site_key=normalized_site_key,
                auth_mode=profile.auth_mode,
                enabled=True,
                headers={profile.header_name: secret_value},
                account_identifier=profile.account_identifier,
            )
        if profile.auth_mode == "bearer_token":
            return SiteAuthContext(
                site_key=normalized_site_key,
                auth_mode=profile.auth_mode,
                enabled=True,
                headers={"Authorization": f"Bearer {secret_value}"},
                account_identifier=profile.account_identifier,
            )
        if profile.auth_mode in {"cookie_header", "browser_session"}:
            return SiteAuthContext(
                site_key=normalized_site_key,
                auth_mode=profile.auth_mode,
                enabled=True,
                headers={"Cookie": secret_value},
                account_identifier=profile.account_identifier,
            )
        if profile.auth_mode == "username_password":
            return SiteAuthContext(
                site_key=normalized_site_key,
                auth_mode=profile.auth_mode,
                enabled=True,
                headers={},
                account_identifier=profile.account_identifier,
                username=profile.account_identifier,
                password=secret_value,
            )
        return SiteAuthContext(site_key=normalized_site_key, auth_mode=profile.auth_mode, enabled=False, headers={})


def mask_site_auth_secret(profile: SiteAuthProfile | None) -> str | None:
    if profile is None or profile.last_four is None:
        return None
    return f"****{profile.last_four}"


def mask_account_identifier(value: str | None) -> str | None:
    if not value:
        return None
    if "@" not in value:
        return value[:1] + "***" if len(value) > 1 else "*"
    local, domain = value.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[:1]}***@{domain}"


def _auth_capabilities_from_declaration(declaration: SiteAdapterDeclaration) -> dict:
    return {
        "supported_auth_modes": list(declaration.supported_auth_modes),
        "auth_storage_notes": declaration.auth_storage_notes,
    }


def _require_known_site_key(declarations: list[SiteAdapterDeclaration], site_key: str) -> str:
    normalized_site_key = site_key.strip().lower()
    if not any(declaration.site_key == normalized_site_key for declaration in declarations):
        raise ValueError("Unknown site adapter")
    return normalized_site_key


def _normalize_auth_mode(auth_mode: str) -> str:
    clean_mode = auth_mode.strip().lower()
    if clean_mode not in SITE_AUTH_MODES:
        raise ValueError("Unsupported site auth mode")
    return clean_mode


def _normalize_header_name(auth_mode: str, header_name: str | None) -> str | None:
    clean_header = (header_name or "").strip()
    if auth_mode != "api_token":
        return None
    if not clean_header:
        raise ValueError("API token auth requires a header name")
    if not HEADER_NAME_RE.match(clean_header):
        raise ValueError("API token header name is invalid")
    if clean_header.lower() in {"authorization", "cookie", "set-cookie"}:
        raise ValueError("Use bearer_token or cookie_header auth mode for this header")
    return clean_header


def _normalize_account_identifier(auth_mode: str, account_identifier: str | None) -> str | None:
    clean_identifier = (account_identifier or "").strip()[:255]
    if auth_mode not in {"username_password", "browser_session"}:
        return None
    if not clean_identifier:
        raise ValueError("Account-linked auth requires an account identifier")
    if "\x00" in clean_identifier:
        raise ValueError("Account identifier contains invalid characters")
    return clean_identifier


def _normalize_secret_value(auth_mode: str, secret_value: str | None) -> str | None:
    clean_secret = (secret_value or "").strip()
    if auth_mode == "none":
        return None
    if auth_mode in REQUIRED_SECRET_AUTH_MODES and not clean_secret:
        raise ValueError("Site auth secret value cannot be empty")
    if auth_mode in OPTIONAL_SECRET_AUTH_MODES and not clean_secret:
        return None
    if "\x00" in clean_secret:
        raise ValueError("Site auth secret value contains invalid characters")
    return clean_secret
