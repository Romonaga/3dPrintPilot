from __future__ import annotations

from pydantic import BaseModel, Field


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


class QueueStatus(BaseModel):
    pending_count: int
    active_count: int
    max_concurrent: int
    supported_job_types: list[str] = []


class OllamaStatus(BaseModel):
    available: bool
    base_url: str
    model: str
    error: str | None = None


class LocalLlmControls(BaseModel):
    max_concurrent_requests: int
    request_timeout_seconds: int
    max_context_tokens: int
    max_output_tokens: int
    min_free_vram_mib: int
    max_gpu_memory_used_percent: float
    max_gpu_temperature_c: float
    oom_cooldown_seconds: int


class ResourceStatusResponse(BaseModel):
    cpu: CpuStatus
    memory: MemoryStatus
    gpu: GpuStatus
    queues: dict[str, QueueStatus] = Field(default_factory=dict)
    ollama: OllamaStatus | None = None
    local_llm: LocalLlmControls | None = None
