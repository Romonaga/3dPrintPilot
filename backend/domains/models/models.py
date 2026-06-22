from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.domains.resources.models import BackgroundJob
from backend.domains.users.models import User

_ = (BackgroundJob, User)


class Model(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="uploaded")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    files: Mapped[list[ModelFile]] = relationship(back_populates="model", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_models_status_created_at", "status", "created_at"),
        Index("ix_models_created_by_created_at", "created_by_user_id", "created_at"),
    )


class ModelFile(Base):
    __tablename__ = "model_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(160))
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_status: Mapped[str] = mapped_column(String(40), nullable=False, default="metadata_only")
    analysis_status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    analysis_job_id: Mapped[int | None] = mapped_column(ForeignKey("background_jobs.id", ondelete="SET NULL"))
    analysis_warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    model: Mapped[Model] = relationship(back_populates="files")
    geometry: Mapped[ModelGeometry | None] = relationship(
        back_populates="model_file",
        cascade="all, delete-orphan",
        uselist=False,
    )
    payload: Mapped[ModelFilePayload | None] = relationship(
        back_populates="model_file",
        cascade="all, delete-orphan",
        uselist=False,
    )

    __table_args__ = (
        Index("ix_model_files_model_id", "model_id"),
        Index("ix_model_files_analysis_status_created_at", "analysis_status", "created_at"),
    )


class ModelFilePayload(Base):
    __tablename__ = "model_file_payloads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_file_id: Mapped[int] = mapped_column(ForeignKey("model_files.id", ondelete="CASCADE"), nullable=False)
    source_project_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_url: Mapped[str] = mapped_column(Text, nullable=False)
    compression: Mapped[str] = mapped_column(String(20), nullable=False)
    compressed_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    original_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compressed_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    compressed_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    model_file: Mapped[ModelFile] = relationship(back_populates="payload")

    __table_args__ = (
        UniqueConstraint("model_file_id", name="uq_model_file_payloads_model_file_id"),
        Index("ix_model_file_payloads_original_sha256", "original_sha256"),
    )


class SourceProjectScan(Base):
    __tablename__ = "source_project_scans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_key: Mapped[str] = mapped_column(String(80), nullable=False)
    source_project_url: Mapped[str] = mapped_column(Text, nullable=False)
    external_project_id: Mapped[str] = mapped_column(String(160), nullable=False)
    project_title: Mapped[str | None] = mapped_column(String(300))
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    files: Mapped[list["SourceProjectScanFile"]] = relationship(back_populates="scan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_source_project_scans_site_project", "site_key", "external_project_id"),
        Index("ix_source_project_scans_source_project_url", "source_project_url"),
        Index("ix_source_project_scans_created_at", "created_at"),
    )


class SourceProjectScanFile(Base):
    __tablename__ = "source_project_scan_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("source_project_scans.id", ondelete="CASCADE"), nullable=False)
    file_id: Mapped[str] = mapped_column(String(160), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    source_file_url: Mapped[str] = mapped_column(Text, nullable=False)
    supported_model_file: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_created_at: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    scan: Mapped[SourceProjectScan] = relationship(back_populates="files")

    __table_args__ = (
        Index("ix_source_project_scan_files_scan_id", "scan_id"),
        Index("ix_source_project_scan_files_file_id", "file_id"),
    )


class ModelGeometry(Base):
    __tablename__ = "model_geometry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_file_id: Mapped[int] = mapped_column(ForeignKey("model_files.id", ondelete="CASCADE"), nullable=False)
    units: Mapped[str] = mapped_column(String(40), nullable=False, default="millimeter")
    size_x_mm: Mapped[float | None] = mapped_column(Float)
    size_y_mm: Mapped[float | None] = mapped_column(Float)
    size_z_mm: Mapped[float | None] = mapped_column(Float)
    min_x_mm: Mapped[float | None] = mapped_column(Float)
    min_y_mm: Mapped[float | None] = mapped_column(Float)
    min_z_mm: Mapped[float | None] = mapped_column(Float)
    max_x_mm: Mapped[float | None] = mapped_column(Float)
    max_y_mm: Mapped[float | None] = mapped_column(Float)
    max_z_mm: Mapped[float | None] = mapped_column(Float)
    volume_mm3: Mapped[float | None] = mapped_column(Float)
    triangle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    model_file: Mapped[ModelFile] = relationship(back_populates="geometry")

    __table_args__ = (
        UniqueConstraint("model_file_id", name="uq_model_geometry_model_file_id"),
        Index("ix_model_geometry_triangle_count", "triangle_count"),
    )
