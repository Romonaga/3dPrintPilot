from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PrinterScanStatus(StrEnum):
    COMPLETED = "completed"


@dataclass(frozen=True)
class DiscoveredPrinter:
    name: str
    host: str
    port: int
    protocol: str
    service_type: str
    confidence: int
    state: str = "discovered"
    evidence: tuple[str, ...] = ()
    scan_result_id: int | None = None
    identity_key: str | None = None
    matched_printer_id: int | None = None


@dataclass(frozen=True)
class PrinterScanSummary:
    status: PrinterScanStatus
    duration_ms: int
    discovered_count: int
    method: str
    scanned_host_count: int = 0
    probe_count: int = 0


@dataclass(frozen=True)
class PrinterScanResult:
    summary: PrinterScanSummary
    printers: tuple[DiscoveredPrinter, ...]
