from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PrinterStatus:
    adapter_type: str
    state: str
    capabilities: dict[str, Any]
    raw_status: dict[str, Any]
    observed_at: datetime


@dataclass(frozen=True)
class MoonrakerFile:
    path: str
    size: int | None
    modified: float | None
    permissions: str | None


@dataclass(frozen=True)
class MoonrakerJobStatus:
    state: str
    filename: str | None
    progress: float | None
    message: str | None
    raw_status: dict[str, Any]
    observed_at: datetime
    bed_temperature: "MoonrakerTemperature | None" = None
    toolheads: tuple["MoonrakerToolheadTelemetry", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MoonrakerTemperature:
    current_c: float | None
    target_c: float | None
    power: float | None = None


@dataclass(frozen=True)
class MoonrakerToolheadTelemetry:
    name: str
    label: str
    index: int
    current_temperature: MoonrakerTemperature | None
    color: str | None = None
    color_source: str | None = None
    material: str | None = None
    material_source: str | None = None
    vendor: str | None = None
    subtype: str | None = None


@dataclass(frozen=True)
class MoonrakerActionResult:
    action: str
    accepted: bool
    raw_response: Any


@dataclass(frozen=True)
class MoonrakerExtensionResult:
    agent: str
    method: str
    accepted: bool
    raw_response: Any


@dataclass(frozen=True)
class MoonrakerCapabilityDiagnostics:
    adapter_type: str
    extension_agents_available: bool
    extension_agents: tuple[dict[str, Any], ...]
    spoolman_available: bool
    spoolman_status: dict[str, Any] | None
    probe_errors: dict[str, str]
    observed_at: datetime


@dataclass(frozen=True)
class SnapmakerU1FilamentSlot:
    index: int
    color: str | None = None
    material: str | None = None
    vendor: str | None = None
    subtype: str | None = None


@dataclass(frozen=True)
class SpoolmanFilamentMetadata:
    color: str | None = None
    material: str | None = None
    vendor: str | None = None


class UnsupportedPrinterControlError(ValueError):
    pass


class InvalidPrintFileError(ValueError):
    pass


class ExtensionMethodNotAllowedError(ValueError):
    pass
