from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CompatibilitySeverity(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


@dataclass(frozen=True)
class PrinterCapabilities:
    name: str
    build_volume_x_mm: float | None = None
    build_volume_y_mm: float | None = None
    build_volume_z_mm: float | None = None
    supported_materials: frozenset[str] = field(default_factory=frozenset)
    max_nozzle_temp_c: float | None = None
    max_bed_temp_c: float | None = None
    enclosed: bool = False


@dataclass(frozen=True)
class ModelRequirements:
    name: str
    size_x_mm: float | None = None
    size_y_mm: float | None = None
    size_z_mm: float | None = None
    material: str | None = None
    nozzle_temp_c: float | None = None
    bed_temp_c: float | None = None
    enclosure_required: bool = False


@dataclass(frozen=True)
class CompatibilityItem:
    code: str
    severity: CompatibilitySeverity
    message: str


@dataclass(frozen=True)
class CompatibilityReport:
    printer_name: str
    model_name: str
    status: CompatibilitySeverity
    items: tuple[CompatibilityItem, ...]
