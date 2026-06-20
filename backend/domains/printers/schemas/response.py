from __future__ import annotations

from pydantic import BaseModel, Field


class PrinterResponse(BaseModel):
    id: int
    name: str
    host: str
    port: int
    protocol: str
    printer_type: str
    state: str
    identity_key: str | None = None
    adapter_type: str | None = None
    capabilities: dict = Field(default_factory=dict)
    credential_configured: bool = False
    last_status: dict = Field(default_factory=dict)
    last_status_at: str | None = None
    build_volume_x_mm: int | None
    build_volume_y_mm: int | None
    build_volume_z_mm: int | None


class DiscoveredPrinterResponse(BaseModel):
    name: str
    host: str
    port: int
    protocol: str
    service_type: str
    confidence: int
    state: str
    evidence: list[str] = Field(default_factory=list)
    scan_result_id: int | None = None
    identity_key: str | None = None
    matched_printer_id: int | None = None


class PrinterStatusResponse(BaseModel):
    printer_id: int
    adapter_type: str
    state: str
    capabilities: dict = Field(default_factory=dict)
    raw_status: dict = Field(default_factory=dict)
    observed_at: str


class PrinterScanSummaryResponse(BaseModel):
    scan_run_id: int | None = None
    status: str
    duration_ms: int
    discovered_count: int
    method: str
    scanned_host_count: int
    probe_count: int


class PrinterEndpointGroupResponse(BaseModel):
    host: str
    name: str
    inferred_type: str
    identity_key: str | None = None
    matched_printer_id: int | None = None
    confidence: int
    ports: list[int]
    capabilities: list[str]
    endpoints: list[DiscoveredPrinterResponse]


class PrinterScanResponse(BaseModel):
    summary: PrinterScanSummaryResponse
    printers: list[DiscoveredPrinterResponse]
    groups: list[PrinterEndpointGroupResponse] = Field(default_factory=list)
