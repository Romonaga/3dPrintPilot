"""foundation users and ai accounting

Revision ID: 0001_foundation
Revises:
Create Date: 2026-06-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("force_password_change", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("uq_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_is_active", "users", ["is_active"])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("uq_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=True)

    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("context_type", sa.String(length=80), nullable=True),
        sa.Column("context_id", sa.String(length=120), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("final_cost_usd", sa.Numeric(12, 8), nullable=True),
        sa.Column("cost_status", sa.String(length=32), nullable=False, server_default="estimated"),
        sa.Column("cost_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost_source", sa.String(length=120), nullable=True),
        sa.Column("cost_discrepancy_usd", sa.Numeric(12, 8), nullable=True),
        sa.Column("reconciliation_run_id", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_usage", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ai_usage_events_user_id_created_at", "ai_usage_events", ["user_id", "created_at"])
    op.create_index("ix_ai_usage_events_provider_model_created_at", "ai_usage_events", ["provider", "model_name", "created_at"])
    op.create_index("ix_ai_usage_events_task_type_created_at", "ai_usage_events", ["task_type", "created_at"])
    op.create_index("ix_ai_usage_events_cost_status_created_at", "ai_usage_events", ["cost_status", "created_at"])

    op.create_table(
        "ai_cost_reconciliation_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="openai"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("estimated_total_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("final_total_usd", sa.Numeric(12, 8), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.create_index("ix_ai_cost_reconciliation_runs_period", "ai_cost_reconciliation_runs", ["period_start", "period_end"])


def downgrade() -> None:
    op.drop_table("ai_cost_reconciliation_runs")
    op.drop_table("ai_usage_events")
    op.drop_table("user_sessions")
    op.drop_table("users")

