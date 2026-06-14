"""site scanning history

Revision ID: 0002_site_scanning
Revises: 0001_foundation
Create Date: 2026-06-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_site_scanning"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_site_adapters",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("site_key", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supports_downloads", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allowed_hosts", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("default_limits", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("robots_terms_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("uq_model_site_adapters_site_key", "model_site_adapters", ["site_key"], unique=True)

    op.create_table(
        "model_site_scan_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("requested_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("site_key", sa.String(length=80), nullable=False),
        sa.Column("start_url", sa.Text(), nullable=False),
        sa.Column("normalized_start_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("stop_reason", sa.String(length=40), nullable=True),
        sa.Column("max_depth", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_pages", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("max_runtime_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("same_domain_only", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("per_host_concurrency", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("queued_url_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scanned_url_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_url_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("limits_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("raw_summary", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_model_site_scan_runs_user_created_at",
        "model_site_scan_runs",
        ["requested_by_user_id", "created_at"],
    )
    op.create_index(
        "ix_model_site_scan_runs_site_key_created_at",
        "model_site_scan_runs",
        ["site_key", "created_at"],
    )
    op.create_index(
        "ix_model_site_scan_runs_status_created_at",
        "model_site_scan_runs",
        ["status", "created_at"],
    )

    op.create_table(
        "model_site_scan_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "scan_run_id",
            sa.BigInteger(),
            sa.ForeignKey("model_site_scan_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("site_key", sa.String(length=80), nullable=False),
        sa.Column("external_model_id", sa.String(length=160), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_url", sa.Text(), nullable=True),
        sa.Column("result_type", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="needs_file"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("inclusion_reason", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_model_site_scan_results_scan_run_id", "model_site_scan_results", ["scan_run_id"])
    op.create_index("ix_model_site_scan_results_source_url", "model_site_scan_results", ["source_url"])
    op.create_index(
        "ix_model_site_scan_results_site_external",
        "model_site_scan_results",
        ["site_key", "external_model_id"],
    )
    op.create_index(
        "ix_model_site_scan_results_status_created_at",
        "model_site_scan_results",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("model_site_scan_results")
    op.drop_table("model_site_scan_runs")
    op.drop_table("model_site_adapters")
