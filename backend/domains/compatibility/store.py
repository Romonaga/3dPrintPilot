from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.domains.compatibility.entities import CompatibilityReport, ModelRequirements, PrinterCapabilities
from backend.domains.compatibility.models import CompatibilityCheck, CompatibilityCheckItem
from backend.domains.printers.models import Printer
from backend.domains.site_scanning.models import ModelSiteScanResult


class CompatibilityStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_candidate_results(self, scan_run_id: int, max_candidates: int) -> list[ModelSiteScanResult]:
        statement = (
            select(ModelSiteScanResult)
            .where(
                ModelSiteScanResult.scan_run_id == scan_run_id,
                ModelSiteScanResult.result_type == "candidate",
            )
            .order_by(ModelSiteScanResult.confidence.desc(), ModelSiteScanResult.id)
            .limit(max_candidates)
        )
        return list(self._session.scalars(statement).all())

    def list_printers(self, printer_ids: list[int] | None = None) -> list[Printer]:
        statement = select(Printer).order_by(Printer.name)
        if printer_ids:
            statement = statement.where(Printer.id.in_(printer_ids))
        return list(self._session.scalars(statement).all())

    def save_report(
        self,
        *,
        scan_result: ModelSiteScanResult,
        printer: Printer,
        report: CompatibilityReport,
        requirements: ModelRequirements,
        duration_ms: int,
        source_type: str = "metadata_only",
        confidence_label: str = "low",
    ) -> CompatibilityCheck:
        check = CompatibilityCheck(
            scan_result_id=scan_result.id,
            printer_id=printer.id,
            status=report.status.value,
            source_type=source_type,
            confidence_label=confidence_label,
            model_title=report.model_name,
            model_url=scan_result.normalized_url,
            printer_name=report.printer_name,
            duration_ms=duration_ms,
            raw_requirements={
                "name": requirements.name,
                "size_x_mm": requirements.size_x_mm,
                "size_y_mm": requirements.size_y_mm,
                "size_z_mm": requirements.size_z_mm,
                "material": requirements.material,
                "nozzle_temp_c": requirements.nozzle_temp_c,
                "bed_temp_c": requirements.bed_temp_c,
                "enclosure_required": requirements.enclosure_required,
            },
        )
        self._session.add(check)
        self._session.flush()
        for item in report.items:
            self._session.add(
                CompatibilityCheckItem(
                    check_id=check.id,
                    code=item.code,
                    severity=item.severity.value,
                    message=item.message,
                )
            )
        self._session.commit()
        self._session.refresh(check)
        return check

    def list_recent_checks(self, limit: int = 50) -> list[CompatibilityCheck]:
        statement = (
            select(CompatibilityCheck)
            .options(selectinload(CompatibilityCheck.items))
            .order_by(CompatibilityCheck.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement).all())


def printer_capabilities(printer: Printer) -> PrinterCapabilities:
    return PrinterCapabilities(
        name=printer.name,
        build_volume_x_mm=printer.build_volume_x_mm,
        build_volume_y_mm=printer.build_volume_y_mm,
        build_volume_z_mm=printer.build_volume_z_mm,
    )


def scan_result_requirements(scan_result: ModelSiteScanResult) -> ModelRequirements:
    return ModelRequirements(name=scan_result.title or scan_result.normalized_url)
