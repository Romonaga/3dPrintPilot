from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
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

    __table_args__ = (
        Index("ix_model_files_model_id", "model_id"),
        Index("ix_model_files_analysis_status_created_at", "analysis_status", "created_at"),
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
