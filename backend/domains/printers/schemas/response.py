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
    capabilities: dict = Field(default_factory=dict)
    build_volume_x_mm: int | None = None
    build_volume_y_mm: int | None = None
    build_volume_z_mm: int | None = None


class PrinterStatusResponse(BaseModel):
    printer_id: int
    adapter_type: str
    state: str
    capabilities: dict = Field(default_factory=dict)
    raw_status: dict = Field(default_factory=dict)
    observed_at: str


class PrinterEngineResponse(BaseModel):
    engine_id: str
    display_name: str
    description: str
    capabilities: dict = Field(default_factory=dict)


class PrinterTemperatureResponse(BaseModel):
    current_c: float | None = None
    target_c: float | None = None
    power: float | None = None


class PrinterToolheadTelemetryResponse(BaseModel):
    name: str
    label: str
    index: int
    current_temperature: PrinterTemperatureResponse | None = None
    color: str | None = None


class PrinterJobStatusResponse(BaseModel):
    printer_id: int
    state: str
    filename: str | None = None
    progress: float | None = None
    message: str | None = None
    bed_temperature: "PrinterTemperatureResponse | None" = None
    toolheads: list["PrinterToolheadTelemetryResponse"] = Field(default_factory=list)
    raw_status: dict = Field(default_factory=dict)
    observed_at: str


class PrinterFileResponse(BaseModel):
    path: str
    size: int | None = None
    modified: float | None = None
    permissions: str | None = None


class PrinterActionResponse(BaseModel):
    printer_id: int
    action: str
    accepted: bool
    raw_response: dict | str | list | None = None


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
