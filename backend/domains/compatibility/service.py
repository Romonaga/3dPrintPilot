from __future__ import annotations

from backend.domains.compatibility.entities import (
    CompatibilityItem,
    CompatibilityReport,
    CompatibilitySeverity,
    ModelRequirements,
    PrinterCapabilities,
)


def check_compatibility(printer: PrinterCapabilities, model: ModelRequirements) -> CompatibilityReport:
    items = [
        _check_build_volume(printer, model),
        _check_material(printer, model),
        _check_nozzle_temperature(printer, model),
        _check_bed_temperature(printer, model),
        _check_enclosure(printer, model),
    ]
    status = _rollup_status(items)
    return CompatibilityReport(
        printer_name=printer.name,
        model_name=model.name,
        status=status,
        items=tuple(items),
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


def _rollup_status(items: list[CompatibilityItem]) -> CompatibilitySeverity:
    if any(item.severity == CompatibilitySeverity.FAIL for item in items):
        return CompatibilitySeverity.FAIL
    if any(item.severity == CompatibilitySeverity.WARNING for item in items):
        return CompatibilitySeverity.WARNING
    return CompatibilitySeverity.PASS
