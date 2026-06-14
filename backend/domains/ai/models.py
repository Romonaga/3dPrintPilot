from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class AiUsageEvent(Base):
    __tablename__ = "ai_usage_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    context_type: Mapped[str | None] = mapped_column(String(80))
    context_id: Mapped[str | None] = mapped_column(String(120))
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=0)
    final_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    cost_status: Mapped[str] = mapped_column(String(32), nullable=False, default="estimated")
    cost_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cost_source: Mapped[str | None] = mapped_column(String(120))
    cost_discrepancy_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    reconciliation_run_id: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_usage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_ai_usage_events_user_id_created_at", "user_id", "created_at"),
        Index("ix_ai_usage_events_provider_model_created_at", "provider", "model_name", "created_at"),
        Index("ix_ai_usage_events_task_type_created_at", "task_type", "created_at"),
        Index("ix_ai_usage_events_cost_status_created_at", "cost_status", "created_at"),
    )


class AiCostReconciliationRun(Base):
    __tablename__ = "ai_cost_reconciliation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="openai")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    estimated_total_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=0)
    final_total_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (Index("ix_ai_cost_reconciliation_runs_period", "period_start", "period_end"),)

