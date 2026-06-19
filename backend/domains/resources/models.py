from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class ResourceSample(Base):
    __tablename__ = "resource_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cpu_load_1m: Mapped[float | None] = mapped_column(Float)
    cpu_load_5m: Mapped[float | None] = mapped_column(Float)
    cpu_load_15m: Mapped[float | None] = mapped_column(Float)
    memory_used_percent: Mapped[float | None] = mapped_column(Float)
    gpu_name: Mapped[str | None] = mapped_column(String(160))
    gpu_utilization_percent: Mapped[float | None] = mapped_column(Float)
    gpu_memory_used_percent: Mapped[float | None] = mapped_column(Float)
    gpu_temperature_c: Mapped[float | None] = mapped_column(Float)
    raw_status: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_resource_samples_created_at", "created_at"),)


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_background_jobs_status_priority", "status", "priority", "available_at"),
        Index("ix_background_jobs_type_status", "job_type", "status"),
    )
