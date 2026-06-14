from __future__ import annotations

from backend.domains.compatibility.entities import CompatibilitySeverity, ModelRequirements, PrinterCapabilities
from backend.domains.compatibility.service import check_compatibility


def test_compatibility_passes_when_model_fits_and_material_limits_match():
    printer = PrinterCapabilities(
        name="Voron 2.4",
        build_volume_x_mm=350,
        build_volume_y_mm=350,
        build_volume_z_mm=330,
        supported_materials=frozenset({"PLA", "PETG", "ABS"}),
        max_nozzle_temp_c=300,
        max_bed_temp_c=120,
        enclosed=True,
    )
    model = ModelRequirements(
        name="gearbox-housing.3mf",
        size_x_mm=120,
        size_y_mm=140,
        size_z_mm=80,
        material="ABS",
        nozzle_temp_c=255,
        bed_temp_c=105,
        enclosure_required=True,
    )

    report = check_compatibility(printer, model)

    assert report.status == CompatibilitySeverity.PASS
    assert all(item.severity == CompatibilitySeverity.PASS for item in report.items)


def test_compatibility_fails_when_model_is_too_tall():
    printer = PrinterCapabilities(
        name="Prusa MK4",
        build_volume_x_mm=250,
        build_volume_y_mm=210,
        build_volume_z_mm=220,
    )
    model = ModelRequirements(name="large-enclosure.stl", size_x_mm=180, size_y_mm=180, size_z_mm=260)

    report = check_compatibility(printer, model)

    assert report.status == CompatibilitySeverity.FAIL
    assert any(item.code == "build_volume" and item.severity == CompatibilitySeverity.FAIL for item in report.items)


def test_compatibility_warns_for_unknown_material_without_blocking_fit():
    printer = PrinterCapabilities(
        name="Bambu X1C",
        build_volume_x_mm=256,
        build_volume_y_mm=256,
        build_volume_z_mm=256,
        max_nozzle_temp_c=300,
        max_bed_temp_c=120,
    )
    model = ModelRequirements(name="clip.stl", size_x_mm=20, size_y_mm=40, size_z_mm=12)

    report = check_compatibility(printer, model)

    assert report.status == CompatibilitySeverity.WARNING
    assert any(item.code == "material" and item.severity == CompatibilitySeverity.WARNING for item in report.items)


def test_compatibility_warns_when_metadata_dimensions_are_unknown():
    printer = PrinterCapabilities(name="Detected Printer", build_volume_x_mm=220, build_volume_y_mm=220, build_volume_z_mm=250)
    model = ModelRequirements(name="metadata-only model")

    report = check_compatibility(printer, model)

    assert report.status == CompatibilitySeverity.WARNING
    assert any(item.code == "build_volume" and item.severity == CompatibilitySeverity.WARNING for item in report.items)
