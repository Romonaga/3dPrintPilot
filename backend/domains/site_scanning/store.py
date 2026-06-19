from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domains.site_scanning.adapters.base import SiteAdapterDeclaration
from backend.domains.site_scanning.entities import ScanResult
from backend.domains.site_scanning.models import ModelSiteAdapter, ModelSiteScanResult, ModelSiteScanRun


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
                allowed_hosts={"hosts": list(declaration.allowed_hosts)},
                default_limits=declaration.default_limits,
                robots_terms_notes=declaration.robots_terms_notes,
            )
            self._session.add(record)
            configured[declaration.site_key] = record
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
