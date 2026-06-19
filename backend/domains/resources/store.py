from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domains.resources.models import BackgroundJob, ResourceSample

SUPPORTED_JOB_TYPES = (
    "network_scan",
    "model_analysis",
    "website_import",
    "ai_enrichment",
    "pricing_refresh",
    "cost_reconciliation",
    "resource_sampling",
)


class ResourceStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_sample(self, status: dict[str, Any]) -> ResourceSample:
        load_average = status.get("cpu", {}).get("load_average") or [None, None, None]
        gpu = status.get("gpu", {})
        sample = ResourceSample(
            cpu_load_1m=load_average[0],
            cpu_load_5m=load_average[1],
            cpu_load_15m=load_average[2],
            memory_used_percent=status.get("memory", {}).get("used_percent"),
            gpu_name=gpu.get("name"),
            gpu_utilization_percent=gpu.get("utilization_percent"),
            gpu_memory_used_percent=gpu.get("memory_used_percent"),
            gpu_temperature_c=gpu.get("temperature_c"),
            raw_status=status,
        )
        self._session.add(sample)
        self._session.commit()
        self._session.refresh(sample)
        return sample

    def enqueue_job(self, job_type: str, payload: dict[str, Any] | None = None, priority: int = 100) -> BackgroundJob:
        if job_type not in SUPPORTED_JOB_TYPES:
            raise ValueError(f"Unsupported job type: {job_type}")
        now = datetime.now(UTC)
        job = BackgroundJob(
            job_type=job_type,
            payload=payload or {},
            priority=priority,
            available_at=now,
            updated_at=now,
        )
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def list_jobs(self, limit: int = 25) -> list[BackgroundJob]:
        statement = (
            select(BackgroundJob)
            .order_by(BackgroundJob.status.asc(), BackgroundJob.priority.asc(), BackgroundJob.created_at.asc())
            .limit(max(1, min(limit, 100)))
        )
        return list(self._session.scalars(statement).all())
