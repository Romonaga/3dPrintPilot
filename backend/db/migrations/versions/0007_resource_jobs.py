"""resource samples and background jobs

Revision ID: 0007_resource_jobs
Revises: 0006_compatibility_checks
Create Date: 2026-06-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_resource_jobs"
down_revision = "0006_compatibility_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resource_samples",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("cpu_load_1m", sa.Float(), nullable=True),
        sa.Column("cpu_load_5m", sa.Float(), nullable=True),
        sa.Column("cpu_load_15m", sa.Float(), nullable=True),
        sa.Column("memory_used_percent", sa.Float(), nullable=True),
        sa.Column("gpu_name", sa.String(length=160), nullable=True),
        sa.Column("gpu_utilization_percent", sa.Float(), nullable=True),
        sa.Column("gpu_memory_used_percent", sa.Float(), nullable=True),
        sa.Column("gpu_temperature_c", sa.Float(), nullable=True),
        sa.Column("raw_status", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_resource_samples_created_at", "resource_samples", ["created_at"])

    op.create_table(
        "background_jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_background_jobs_status_priority", "background_jobs", ["status", "priority", "available_at"])
    op.create_index("ix_background_jobs_type_status", "background_jobs", ["job_type", "status"])


def downgrade() -> None:
    op.drop_table("background_jobs")
    op.drop_table("resource_samples")
