from __future__ import annotations

from backend.domains.compatibility.entities import (
    CompatibilityItem,
    CompatibilityReport,
    CompatibilitySeverity,
    ModelRequirements,
    PrinterCapabilities,
)

MATERIAL_PROFILES = {
    "PLA": {"nozzle_temp_c": 210, "bed_temp_c": 60, "enclosure_required": False},
    "PETG": {"nozzle_temp_c": 245, "bed_temp_c": 80, "enclosure_required": False},
    "ABS": {"nozzle_temp_c": 255, "bed_temp_c": 105, "enclosure_required": True},
    "ASA": {"nozzle_temp_c": 260, "bed_temp_c": 105, "enclosure_required": True},
    "TPU": {"nozzle_temp_c": 230, "bed_temp_c": 50, "enclosure_required": False, "flexible": True},
    "NYLON": {"nozzle_temp_c": 270, "bed_temp_c": 90, "enclosure_required": True},
    "PA-CF": {"nozzle_temp_c": 285, "bed_temp_c": 100, "enclosure_required": True, "abrasive": True},
    "PETG-CF": {"nozzle_temp_c": 260, "bed_temp_c": 80, "enclosure_required": False, "abrasive": True},
}


def check_compatibility(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityReport:
    model = _apply_material_profile(model)
    items = [
        _check_build_volume(printer, model),
        _check_file_format(printer, model),
        _check_material(printer, model),
        _check_nozzle_diameter(printer, model),
        _check_nozzle_temperature(printer, model),
        _check_bed_temperature(printer, model),
        _check_enclosure(printer, model),
        _check_abrasive_material(printer, model),
        _check_flexible_material(printer, model),
        _check_multi_material(printer, model),
        _check_printer_status(printer),
    ]
    status = _rollup_status(items)
    return CompatibilityReport(
        printer_name=printer.name,
        model_name=model.name,
        status=status,
        items=tuple(items),
    )


def _apply_material_profile(model: ModelRequirements) -> ModelRequirements:
    if not model.material:
        return model
    profile = MATERIAL_PROFILES.get(model.material.upper())
    if profile is None:
        return model
    return ModelRequirements(
        name=model.name,
        size_x_mm=model.size_x_mm,
        size_y_mm=model.size_y_mm,
        size_z_mm=model.size_z_mm,
        material=model.material,
        nozzle_temp_c=model.nozzle_temp_c if model.nozzle_temp_c is not None else profile.get("nozzle_temp_c"),
        bed_temp_c=model.bed_temp_c if model.bed_temp_c is not None else profile.get("bed_temp_c"),
        enclosure_required=model.enclosure_required or bool(profile.get("enclosure_required")),
        file_format=model.file_format,
        nozzle_diameter_mm=model.nozzle_diameter_mm,
        abrasive=model.abrasive or bool(profile.get("abrasive")),
        flexible=model.flexible or bool(profile.get("flexible")),
        color_count=model.color_count,
        source_type=model.source_type,
    )


def _check_build_volume(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if (
        model.size_x_mm is None
        or model.size_y_mm is None
        or model.size_z_mm is None
        or printer.build_volume_x_mm is None
        or printer.build_volume_y_mm is None
        or printer.build_volume_z_mm is None
    ):
        return CompatibilityItem(
            code="build_volume",
            severity=CompatibilitySeverity.WARNING,
            message="Build volume cannot be verified until model dimensions and printer volume are known.",
        )
    model_xy = sorted([model.size_x_mm, model.size_y_mm])
    printer_xy = sorted([printer.build_volume_x_mm, printer.build_volume_y_mm])
    xy_fits = model_xy[0] <= printer_xy[0] and model_xy[1] <= printer_xy[1]
    z_fits = model.size_z_mm <= printer.build_volume_z_mm
    if xy_fits and z_fits:
        return CompatibilityItem(
            code="build_volume",
            severity=CompatibilitySeverity.PASS,
            message="Model fits within the printer build volume.",
        )
    return CompatibilityItem(
        code="build_volume",
        severity=CompatibilitySeverity.FAIL,
        message=(
            "Model exceeds build volume: "
            f"{model.size_x_mm:g} x {model.size_y_mm:g} x {model.size_z_mm:g} mm vs "
            f"{printer.build_volume_x_mm:g} x {printer.build_volume_y_mm:g} x {printer.build_volume_z_mm:g} mm."
        ),
        )


def _check_file_format(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if not model.file_format:
        return CompatibilityItem(
            code="file_format",
            severity=CompatibilitySeverity.WARNING,
            message="Model file format is unknown.",
        )
    supported = {value.lower() for value in printer.supported_file_formats}
    file_format = model.file_format.lower()
    if not supported or file_format in supported:
        return CompatibilityItem(
            code="file_format",
            severity=CompatibilitySeverity.PASS,
            message=f"{file_format.upper()} is supported by this printer workflow.",
        )
    return CompatibilityItem(
        code="file_format",
        severity=CompatibilitySeverity.WARNING,
        message=f"{file_format.upper()} is not listed as supported by this printer workflow.",
    )


def _check_material(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if not model.material:
        return CompatibilityItem(
            code="material",
            severity=CompatibilitySeverity.WARNING,
            message="Material requirement is unknown.",
        )
    material = model.material.upper()
    supported = {value.upper() for value in printer.supported_materials}
    if not supported or material in supported:
        return CompatibilityItem(
            code="material",
            severity=CompatibilitySeverity.PASS,
            message=f"{material} is supported by this printer profile.",
        )
    return CompatibilityItem(
        code="material",
        severity=CompatibilitySeverity.WARNING,
        message=f"{material} is not listed in this printer profile.",
    )


def _check_nozzle_diameter(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if model.nozzle_diameter_mm is None or printer.nozzle_diameter_mm is None:
        return CompatibilityItem(
            code="nozzle_diameter",
            severity=CompatibilitySeverity.WARNING,
            message="Nozzle diameter requirement or printer nozzle size is unknown.",
        )
    if model.nozzle_diameter_mm >= printer.nozzle_diameter_mm:
        return CompatibilityItem(
            code="nozzle_diameter",
            severity=CompatibilitySeverity.PASS,
            message="Model nozzle requirement is compatible with the installed nozzle.",
        )
    return CompatibilityItem(
        code="nozzle_diameter",
        severity=CompatibilitySeverity.WARNING,
        message=f"Model expects a nozzle at or below {model.nozzle_diameter_mm:g} mm; printer profile is {printer.nozzle_diameter_mm:g} mm.",
    )


def _check_nozzle_temperature(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if model.nozzle_temp_c is None or printer.max_nozzle_temp_c is None:
        return CompatibilityItem(
            code="nozzle_temperature",
            severity=CompatibilitySeverity.WARNING,
            message="Nozzle temperature limit or requirement is unknown.",
        )
    if model.nozzle_temp_c <= printer.max_nozzle_temp_c:
        return CompatibilityItem(
            code="nozzle_temperature",
            severity=CompatibilitySeverity.PASS,
            message="Nozzle temperature requirement is within printer limits.",
        )
    return CompatibilityItem(
        code="nozzle_temperature",
        severity=CompatibilitySeverity.FAIL,
        message=f"Required nozzle temperature {model.nozzle_temp_c:g} C exceeds printer limit {printer.max_nozzle_temp_c:g} C.",
    )


def _check_bed_temperature(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if model.bed_temp_c is None or printer.max_bed_temp_c is None:
        return CompatibilityItem(
            code="bed_temperature",
            severity=CompatibilitySeverity.WARNING,
            message="Bed temperature limit or requirement is unknown.",
        )
    if model.bed_temp_c <= printer.max_bed_temp_c:
        return CompatibilityItem(
            code="bed_temperature",
            severity=CompatibilitySeverity.PASS,
            message="Bed temperature requirement is within printer limits.",
        )
    return CompatibilityItem(
        code="bed_temperature",
        severity=CompatibilitySeverity.FAIL,
        message=f"Required bed temperature {model.bed_temp_c:g} C exceeds printer limit {printer.max_bed_temp_c:g} C.",
    )


def _check_enclosure(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if not model.enclosure_required:
        return CompatibilityItem(
            code="enclosure",
            severity=CompatibilitySeverity.PASS,
        message="No enclosure requirement declared.",
        )
    if printer.enclosed:
        return CompatibilityItem(
            code="enclosure",
            severity=CompatibilitySeverity.PASS,
            message="Printer has an enclosure.",
        )
    return CompatibilityItem(
        code="enclosure",
        severity=CompatibilitySeverity.WARNING,
        message="Model/material may require an enclosure, but this printer profile is open-frame.",
    )


def _check_abrasive_material(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if not model.abrasive:
        return CompatibilityItem(
            code="abrasive_material",
            severity=CompatibilitySeverity.PASS,
            message="No abrasive material requirement declared.",
        )
    if printer.hardened_nozzle:
        return CompatibilityItem(
            code="abrasive_material",
            severity=CompatibilitySeverity.PASS,
            message="Printer profile indicates a hardened nozzle for abrasive material.",
        )
    return CompatibilityItem(
        code="abrasive_material",
        severity=CompatibilitySeverity.WARNING,
        message="Abrasive material should use a hardened nozzle; this printer profile does not confirm one.",
    )


def _check_flexible_material(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if not model.flexible:
        return CompatibilityItem(
            code="flexible_material",
            severity=CompatibilitySeverity.PASS,
            message="No flexible material requirement declared.",
        )
    if printer.flexible_capable:
        return CompatibilityItem(
            code="flexible_material",
            severity=CompatibilitySeverity.PASS,
            message="Printer profile indicates flexible material support.",
        )
    return CompatibilityItem(
        code="flexible_material",
        severity=CompatibilitySeverity.WARNING,
        message="Flexible material may need a constrained/direct drive path; this printer profile does not confirm support.",
    )


def _check_multi_material(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityItem:
    if model.color_count <= 1:
        return CompatibilityItem(
            code="multi_material",
            severity=CompatibilitySeverity.PASS,
            message="No multi-material or multi-color requirement declared.",
        )
    if printer.color_count >= model.color_count:
        return CompatibilityItem(
            code="multi_material",
            severity=CompatibilitySeverity.PASS,
            message="Printer profile has enough material/color channels.",
        )
    return CompatibilityItem(
        code="multi_material",
        severity=CompatibilitySeverity.WARNING,
        message=f"Model expects {model.color_count} material/color channels; printer profile lists {printer.color_count}.",
    )


def _check_printer_status(printer: PrinterCapabilities) -> CompatibilityItem:
    if printer.online is True:
        return CompatibilityItem(
            code="printer_status",
            severity=CompatibilitySeverity.PASS,
            message="Printer status evidence indicates the printer is online.",
        )
    if printer.online is False:
        return CompatibilityItem(
            code="printer_status",
            severity=CompatibilitySeverity.WARNING,
            message="Printer status evidence indicates the printer is offline.",
        )
    return CompatibilityItem(
        code="printer_status",
        severity=CompatibilitySeverity.WARNING,
        message="Printer online status is unknown.",
    )


def _rollup_status(items: list[CompatibilityItem]) -> CompatibilitySeverity:
    if any(item.severity == CompatibilitySeverity.FAIL for item in items):
        return CompatibilitySeverity.FAIL
    if any(item.severity == CompatibilitySeverity.WARNING for item in items):
        return CompatibilitySeverity.WARNING
    return CompatibilitySeverity.PASS
