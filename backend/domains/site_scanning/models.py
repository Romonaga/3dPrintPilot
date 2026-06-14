from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.domains.users.models import User

_ = User


class ModelSiteAdapter(Base):
    __tablename__ = "model_site_adapters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_downloads: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_hosts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    default_limits: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    robots_terms_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ModelSiteScanRun(Base):
    __tablename__ = "model_site_scan_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    site_key: Mapped[str] = mapped_column(String(80), nullable=False)
    start_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_start_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    stop_reason: Mapped[str | None] = mapped_column(String(40))
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    max_runtime_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    same_domain_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    per_host_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    queued_url_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanned_url_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_url_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    limits_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    results: Mapped[list[ModelSiteScanResult]] = relationship(
        back_populates="scan_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_model_site_scan_runs_user_created_at", "requested_by_user_id", "created_at"),
        Index("ix_model_site_scan_runs_site_key_created_at", "site_key", "created_at"),
        Index("ix_model_site_scan_runs_status_created_at", "status", "created_at"),
    )


class ModelSiteScanResult(Base):
    __tablename__ = "model_site_scan_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scan_run_id: Mapped[int] = mapped_column(ForeignKey("model_site_scan_runs.id", ondelete="CASCADE"), nullable=False)
    site_key: Mapped[str] = mapped_column(String(80), nullable=False)
    external_model_id: Mapped[str | None] = mapped_column(String(160))
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(300))
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_url: Mapped[str | None] = mapped_column(Text)
    result_type: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="needs_file")
    confidence: Mapped[float | None] = mapped_column(Float)
    inclusion_reason: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    scan_run: Mapped[ModelSiteScanRun] = relationship(back_populates="results")

    __table_args__ = (
        Index("ix_model_site_scan_results_scan_run_id", "scan_run_id"),
        Index("ix_model_site_scan_results_source_url", "source_url"),
        Index("ix_model_site_scan_results_site_external", "site_key", "external_model_id"),
        Index("ix_model_site_scan_results_status_created_at", "status", "created_at"),
    )
