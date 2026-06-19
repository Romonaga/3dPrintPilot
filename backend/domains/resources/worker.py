from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from heapq import heappop, heappush
from itertools import count
from typing import Any


@dataclass(frozen=True)
class LocalLlmAdmissionPolicy:
    max_concurrent_requests: int = 1
    request_timeout_seconds: int = 120
    max_context_tokens: int = 8192
    max_output_tokens: int = 2048
    min_free_vram_mib: int = 4096
    max_gpu_memory_used_percent: float = 88.0
    max_gpu_temperature_c: float = 82.0
    oom_cooldown_seconds: int = 300


@dataclass(frozen=True)
class QueueState:
    active_count: int = 0
    pending_count: int = 0
    cooldown_until: datetime | None = None


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    reason: str
    retry_after_seconds: int | None = None


class LocalLlmRequestGate:
    def __init__(self, policy: LocalLlmAdmissionPolicy | None = None) -> None:
        self.policy = policy or LocalLlmAdmissionPolicy()

    def evaluate(
        self,
        gpu_status: dict[str, Any],
        queue_state: QueueState,
        requested_context_tokens: int,
        requested_output_tokens: int,
    ) -> AdmissionDecision:
        now = datetime.now(UTC)
        if queue_state.cooldown_until is not None and queue_state.cooldown_until > now:
            retry_after = int((queue_state.cooldown_until - now).total_seconds())
            return AdmissionDecision(False, "oom_cooldown", retry_after_seconds=max(1, retry_after))
        if queue_state.active_count >= self.policy.max_concurrent_requests:
            return AdmissionDecision(False, "concurrency_limit")
        if requested_context_tokens > self.policy.max_context_tokens:
            return AdmissionDecision(False, "context_limit")
        if requested_output_tokens > self.policy.max_output_tokens:
            return AdmissionDecision(False, "output_limit")
        if not gpu_status.get("available", False):
            return AdmissionDecision(False, "gpu_unavailable")

        memory_used_percent = gpu_status.get("memory_used_percent")
        if memory_used_percent is not None and memory_used_percent >= self.policy.max_gpu_memory_used_percent:
            return AdmissionDecision(False, "vram_pressure")
        temperature_c = gpu_status.get("temperature_c")
        if temperature_c is not None and temperature_c >= self.policy.max_gpu_temperature_c:
            return AdmissionDecision(False, "temperature_pressure")
        memory_total = gpu_status.get("memory_total_mib")
        memory_used = gpu_status.get("memory_used_mib")
        if memory_total is not None and memory_used is not None:
            if memory_total - memory_used < self.policy.min_free_vram_mib:
                return AdmissionDecision(False, "free_vram_limit")
        return AdmissionDecision(True, "admitted")


class WorkQueue:
    def __init__(self) -> None:
        self._counter = count()
        self._items: list[tuple[int, int, str, dict[str, Any]]] = []

    def push(self, job_type: str, payload: dict[str, Any] | None = None, priority: int = 100) -> None:
        heappush(self._items, (priority, next(self._counter), job_type, payload or {}))

    def pop(self) -> tuple[str, dict[str, Any]] | None:
        if not self._items:
            return None
        _, _, job_type, payload = heappop(self._items)
        return job_type, payload

    @property
    def pending_count(self) -> int:
        return len(self._items)
