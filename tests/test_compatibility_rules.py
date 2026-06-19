from __future__ import annotations

from backend.domains.compatibility.entities import CompatibilitySeverity, ModelRequirements, PrinterCapabilities
from backend.domains.compatibility.service import check_compatibility
from backend.domains.compatibility.store import scan_result_requirements


def test_compatibility_passes_when_model_fits_and_material_limits_match():
    printer = PrinterCapabilities(
        name="Voron 2.4",
        build_volume_x_mm=350,
        build_volume_y_mm=350,
        build_volume_z_mm=330,
        supported_materials=frozenset({"PLA", "PETG", "ABS"}),
        max_nozzle_temp_c=300,
        max_bed_temp_c=120,
        nozzle_diameter_mm=0.4,
        hardened_nozzle=True,
        flexible_capable=True,
        color_count=4,
        supported_file_formats=frozenset({"stl", "3mf"}),
        enclosed=True,
        online=True,
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
        file_format="3mf",
        nozzle_diameter_mm=0.4,
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


def test_material_profile_supplies_abs_temperature_and_enclosure_requirements():
    printer = PrinterCapabilities(
        name="Open frame",
        build_volume_x_mm=220,
        build_volume_y_mm=220,
        build_volume_z_mm=250,
        supported_materials=frozenset({"ABS"}),
        max_nozzle_temp_c=260,
        max_bed_temp_c=110,
        supported_file_formats=frozenset({"stl"}),
    )
    model = ModelRequirements(name="bracket.stl", size_x_mm=20, size_y_mm=20, size_z_mm=20, material="ABS", file_format="stl")

    report = check_compatibility(printer, model)

    assert report.status == CompatibilitySeverity.WARNING
    assert any(item.code == "enclosure" and item.severity == CompatibilitySeverity.WARNING for item in report.items)


def test_compatibility_warns_for_unsupported_file_format_and_nozzle_mismatch():
    printer = PrinterCapabilities(
        name="STL-only printer",
        build_volume_x_mm=250,
        build_volume_y_mm=250,
        build_volume_z_mm=250,
        nozzle_diameter_mm=0.6,
        supported_file_formats=frozenset({"stl"}),
    )
    model = ModelRequirements(
        name="detail.3mf",
        size_x_mm=30,
        size_y_mm=30,
        size_z_mm=30,
        file_format="3mf",
        nozzle_diameter_mm=0.25,
    )

    report = check_compatibility(printer, model)

    assert any(item.code == "file_format" and item.severity == CompatibilitySeverity.WARNING for item in report.items)
    assert any(item.code == "nozzle_diameter" and item.severity == CompatibilitySeverity.WARNING for item in report.items)


def test_compatibility_warns_for_abrasive_flexible_and_multi_color_constraints():
    printer = PrinterCapabilities(
        name="Basic printer",
        build_volume_x_mm=250,
        build_volume_y_mm=250,
        build_volume_z_mm=250,
        supported_materials=frozenset({"TPU", "PA-CF"}),
        max_nozzle_temp_c=300,
        max_bed_temp_c=110,
        color_count=1,
    )
    model = ModelRequirements(
        name="wear-pad.stl",
        size_x_mm=30,
        size_y_mm=30,
        size_z_mm=8,
        material="PA-CF",
        file_format="stl",
        abrasive=True,
        flexible=True,
        color_count=2,
    )

    report = check_compatibility(printer, model)

    assert any(item.code == "abrasive_material" and item.severity == CompatibilitySeverity.WARNING for item in report.items)
    assert any(item.code == "flexible_material" and item.severity == CompatibilitySeverity.WARNING for item in report.items)
    assert any(item.code == "multi_material" and item.severity == CompatibilitySeverity.WARNING for item in report.items)


def test_offline_status_lowers_confidence_without_failing_fit():
    printer = PrinterCapabilities(
        name="Offline printer",
        build_volume_x_mm=250,
        build_volume_y_mm=250,
        build_volume_z_mm=250,
        online=False,
    )
    model = ModelRequirements(name="cube.stl", size_x_mm=20, size_y_mm=20, size_z_mm=20, file_format="stl")

    report = check_compatibility(printer, model)

    assert report.status == CompatibilitySeverity.WARNING
    assert any(item.code == "printer_status" and item.severity == CompatibilitySeverity.WARNING for item in report.items)


def test_metadata_requirements_are_read_from_scan_candidate_evidence():
    scan_result = type(
        "ScanResult",
        (),
        {
            "title": "ABS bracket",
            "normalized_url": "https://example.com/model/abs-bracket",
            "raw_payload": {"metadata_only": True},
            "evidence": {
                "requirements": {
                    "material": "ABS",
                    "file_format": "3mf",
                    "nozzle_diameter_mm": 0.4,
                    "color_count": 2,
                }
            },
        },
    )()

    requirements = scan_result_requirements(scan_result)

    assert requirements.source_type == "metadata_only"
    assert requirements.material == "ABS"
    assert requirements.file_format == "3mf"
    assert requirements.nozzle_diameter_mm == 0.4
    assert requirements.color_count == 2
