from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.domains.compatibility.entities import CompatibilityReport, ModelRequirements, PrinterCapabilities
from backend.domains.compatibility.models import CompatibilityCheck, CompatibilityCheckItem
from backend.domains.models.models import Model, ModelFile
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

    def requirements_for_scan_result(self, scan_result: ModelSiteScanResult) -> ModelRequirements:
        uploaded = self._find_uploaded_model(scan_result.normalized_url)
        if uploaded is None:
            return scan_result_requirements(scan_result)
        model_file = uploaded.files[0] if uploaded.files else None
        geometry = model_file.geometry if model_file is not None else None
        if geometry is None:
            return scan_result_requirements(scan_result)
        raw_metadata = model_file.raw_metadata or {}
        return ModelRequirements(
            name=uploaded.title,
            size_x_mm=geometry.size_x_mm,
            size_y_mm=geometry.size_y_mm,
            size_z_mm=geometry.size_z_mm,
            material=_clean_string(raw_metadata.get("material")),
            nozzle_temp_c=_float_or_none(raw_metadata.get("nozzle_temp_c")),
            bed_temp_c=_float_or_none(raw_metadata.get("bed_temp_c")),
            enclosure_required=bool(raw_metadata.get("enclosure_required", False)),
            file_format=model_file.file_format,
            nozzle_diameter_mm=_float_or_none(raw_metadata.get("nozzle_diameter_mm")),
            abrasive=bool(raw_metadata.get("abrasive", False)),
            flexible=bool(raw_metadata.get("flexible", False)),
            color_count=max(1, int(raw_metadata.get("color_count", 1) or 1)),
            source_type="geometry",
        )

    def _find_uploaded_model(self, normalized_url: str) -> Model | None:
        statement = (
            select(Model)
            .options(selectinload(Model.files).selectinload(ModelFile.geometry))
            .where(Model.source_url == normalized_url)
            .order_by(Model.created_at.desc(), Model.id.desc())
            .limit(1)
        )
        return self._session.scalars(statement).first()

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
                "file_format": requirements.file_format,
                "nozzle_diameter_mm": requirements.nozzle_diameter_mm,
                "abrasive": requirements.abrasive,
                "flexible": requirements.flexible,
                "color_count": requirements.color_count,
                "source_type": requirements.source_type,
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
    capabilities = printer.capabilities or {}
    materials = capabilities.get("supported_materials") or capabilities.get("materials") or ()
    formats = capabilities.get("supported_file_formats") or ("stl", "3mf")
    online = _online_status(printer.last_status or {})
    return PrinterCapabilities(
        name=printer.name,
        build_volume_x_mm=printer.build_volume_x_mm,
        build_volume_y_mm=printer.build_volume_y_mm,
        build_volume_z_mm=printer.build_volume_z_mm,
        supported_materials=frozenset(str(material).upper() for material in materials),
        max_nozzle_temp_c=_float_or_none(capabilities.get("max_nozzle_temp_c")),
        max_bed_temp_c=_float_or_none(capabilities.get("max_bed_temp_c")),
        nozzle_diameter_mm=_float_or_none(capabilities.get("nozzle_diameter_mm")),
        hardened_nozzle=bool(capabilities.get("hardened_nozzle", False)),
        flexible_capable=bool(capabilities.get("flexible_capable", False)),
        color_count=max(1, int(capabilities.get("color_count", 1) or 1)),
        supported_file_formats=frozenset(str(file_format).lower() for file_format in formats),
        enclosed=bool(capabilities.get("enclosed", False)),
        online=online,
    )


def scan_result_requirements(scan_result: ModelSiteScanResult) -> ModelRequirements:
    raw_payload = scan_result.raw_payload or {}
    evidence = scan_result.evidence or {}
    requirements = evidence.get("requirements") or raw_payload.get("requirements") or {}
    filename = str(raw_payload.get("filename") or scan_result.normalized_url)
    file_format = _clean_string(requirements.get("file_format")) or _file_format_from_name(filename)
    material = _clean_string(requirements.get("material") or raw_payload.get("material") or evidence.get("material"))
    return ModelRequirements(
        name=scan_result.title or scan_result.normalized_url,
        size_x_mm=_float_or_none(requirements.get("size_x_mm")),
        size_y_mm=_float_or_none(requirements.get("size_y_mm")),
        size_z_mm=_float_or_none(requirements.get("size_z_mm")),
        material=material,
        nozzle_temp_c=_float_or_none(requirements.get("nozzle_temp_c")),
        bed_temp_c=_float_or_none(requirements.get("bed_temp_c")),
        enclosure_required=bool(requirements.get("enclosure_required", False)),
        file_format=file_format,
        nozzle_diameter_mm=_float_or_none(requirements.get("nozzle_diameter_mm")),
        abrasive=bool(requirements.get("abrasive", False)),
        flexible=bool(requirements.get("flexible", False)),
        color_count=max(1, int(requirements.get("color_count", 1) or 1)),
        source_type="metadata_only",
    )


def report_source_type(requirements: ModelRequirements) -> str:
    return "geometry" if requirements.source_type == "geometry" else "metadata_only"


def report_confidence_label(requirements: ModelRequirements) -> str:
    if requirements.source_type == "geometry" and requirements.size_x_mm is not None:
        return "high"
    if requirements.material or requirements.file_format:
        return "medium"
    return "low"


def _file_format_from_name(value: str) -> str | None:
    lowered = value.lower().split("?", 1)[0]
    if lowered.endswith(".3mf"):
        return "3mf"
    if lowered.endswith(".stl"):
        return "stl"
    return None


def _clean_string(value) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _online_status(last_status: dict) -> bool | None:
    state = str(last_status.get("state") or last_status.get("status") or "").lower()
    if state in {"online", "ready", "printing", "paused", "idle"}:
        return True
    if state in {"offline", "unreachable", "error"}:
        return False
    return None
