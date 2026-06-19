from __future__ import annotations

from pydantic import BaseModel, Field


class CreatePrinterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=80, ge=1, le=65535)
    protocol: str = Field(default="http", min_length=2, max_length=40)
    printer_type: str = Field(default="unknown", min_length=1, max_length=80)
    build_volume_x_mm: int | None = Field(default=None, ge=1, le=2000)
    build_volume_y_mm: int | None = Field(default=None, ge=1, le=2000)
    build_volume_z_mm: int | None = Field(default=None, ge=1, le=2000)


class UpdatePrinterRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    protocol: str | None = Field(default=None, min_length=2, max_length=40)
    printer_type: str | None = Field(default=None, min_length=1, max_length=80)
    build_volume_x_mm: int | None = Field(default=None, ge=1, le=2000)
    build_volume_y_mm: int | None = Field(default=None, ge=1, le=2000)
    build_volume_z_mm: int | None = Field(default=None, ge=1, le=2000)


class ConfirmDiscoveredPrinterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    protocol: str = Field(default="http", min_length=2, max_length=40)
    service_type: str = Field(default="unknown", min_length=1, max_length=160)
    confidence: int = Field(default=50, ge=0, le=100)
    scan_result_id: int | None = None
    build_volume_x_mm: int | None = Field(default=None, ge=1, le=2000)
    build_volume_y_mm: int | None = Field(default=None, ge=1, le=2000)
    build_volume_z_mm: int | None = Field(default=None, ge=1, le=2000)


class PrinterScanRequest(BaseModel):
    timeout_seconds: float = Field(default=20.0, ge=1.0, le=60.0)
    scan_method: str = Field(default="combined", pattern="^(mdns|http_probe|combined)$")
    target_cidr: str | None = Field(default=None, max_length=64)
    max_hosts: int = Field(default=254, ge=1, le=512)
    ports: list[int] = Field(default_factory=lambda: [80, 443, 4408, 5000, 6000, 7125, 8000, 8080, 8081, 8883], max_length=10)
    connect_timeout_seconds: float = Field(default=2.0, ge=0.1, le=5.0)
