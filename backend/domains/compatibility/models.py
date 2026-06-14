from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class CompatibilityCheck(Base):
    __tablename__ = "compatibility_checks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scan_result_id: Mapped[int] = mapped_column(
        ForeignKey("model_site_scan_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="metadata_only")
    confidence_label: Mapped[str] = mapped_column(String(40), nullable=False, default="low")
    model_title: Mapped[str] = mapped_column(String(300), nullable=False)
    model_url: Mapped[str] = mapped_column(Text, nullable=False)
    printer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_requirements: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items: Mapped[list["CompatibilityCheckItem"]] = relationship(
        back_populates="check",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_compatibility_checks_scan_result_id", "scan_result_id"),
        Index("ix_compatibility_checks_printer_id_created_at", "printer_id", "created_at"),
        Index("ix_compatibility_checks_status_created_at", "status", "created_at"),
    )


class CompatibilityCheckItem(Base):
    __tablename__ = "compatibility_check_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    check_id: Mapped[int] = mapped_column(ForeignKey("compatibility_checks.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    check: Mapped[CompatibilityCheck] = relationship(back_populates="items")

    __table_args__ = (Index("ix_compatibility_check_items_check_id", "check_id"),)
