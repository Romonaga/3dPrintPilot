from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.domains.users.models import User

_ = User


class Printer(Base):
    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, default="http")
    printer_type: Mapped[str] = mapped_column(String(80), nullable=False, default="unknown")
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    identity_key: Mapped[str | None] = mapped_column(String(255))
    adapter_type: Mapped[str | None] = mapped_column(String(80))
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    credential_secret_name: Mapped[str | None] = mapped_column(String(120))
    last_status: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    build_volume_x_mm: Mapped[int | None] = mapped_column(Integer)
    build_volume_y_mm: Mapped[int | None] = mapped_column(Integer)
    build_volume_z_mm: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_printers_owner_user_id", "owner_user_id"),
        Index("ix_printers_host_port", "host", "port"),
        Index("uq_printers_identity_key", "identity_key", unique=True),
    )


class NetworkScanRun(Base):
    __tablename__ = "network_scan_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed")
    method: Mapped[str] = mapped_column(String(80), nullable=False, default="mdns")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanned_host_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    probe_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    results: Mapped[list[NetworkScanResult]] = relationship(back_populates="scan_run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_network_scan_runs_user_created_at", "requested_by_user_id", "created_at"),
        Index("ix_network_scan_runs_status_created_at", "status", "created_at"),
    )


class NetworkScanResult(Base):
    __tablename__ = "network_scan_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scan_run_id: Mapped[int] = mapped_column(ForeignKey("network_scan_runs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, default="http")
    service_type: Mapped[str] = mapped_column(String(160), nullable=False)
    identity_key: Mapped[str | None] = mapped_column(String(255))
    matched_printer_id: Mapped[int | None] = mapped_column(ForeignKey("printers.id", ondelete="SET NULL"))
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="discovered")
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    build_volume_x_mm: Mapped[int | None] = mapped_column(Integer)
    build_volume_y_mm: Mapped[int | None] = mapped_column(Integer)
    build_volume_z_mm: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    scan_run: Mapped[NetworkScanRun] = relationship(back_populates="results")

    __table_args__ = (
        Index("ix_network_scan_results_scan_run_id", "scan_run_id"),
        Index("ix_network_scan_results_host", "host"),
        Index("ix_network_scan_results_identity_key", "identity_key"),
        Index("ix_network_scan_results_matched_printer_id", "matched_printer_id"),
    )
