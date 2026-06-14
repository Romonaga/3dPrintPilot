from __future__ import annotations

from pydantic import BaseModel


class GpuStatus(BaseModel):
    available: bool
    name: str | None = None
    utilization_percent: float | None = None
    memory_used_mib: float | None = None
    memory_total_mib: float | None = None
    memory_used_percent: float | None = None
    temperature_c: float | None = None
    error: str | None = None


class CpuStatus(BaseModel):
    cores: int
    load_average: list[float] | None = None


class MemoryStatus(BaseModel):
    total_bytes: int | None = None
    available_bytes: int | None = None
    used_percent: float | None = None


class ResourceStatusResponse(BaseModel):
    cpu: CpuStatus
    memory: MemoryStatus
    gpu: GpuStatus

