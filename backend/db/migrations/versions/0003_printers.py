"""printer inventory and scan history

Revision ID: 0003_printers
Revises: 0002_site_scanning
Create Date: 2026-06-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_printers"
down_revision = "0002_site_scanning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "printers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False, server_default="http"),
        sa.Column("printer_type", sa.String(length=80), nullable=False, server_default="unknown"),
        sa.Column("state", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("build_volume_x_mm", sa.Integer(), nullable=True),
        sa.Column("build_volume_y_mm", sa.Integer(), nullable=True),
        sa.Column("build_volume_z_mm", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_printers_owner_user_id", "printers", ["owner_user_id"])
    op.create_index("ix_printers_host_port", "printers", ["host", "port"])

    op.create_table(
        "network_scan_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("requested_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="completed"),
        sa.Column("method", sa.String(length=80), nullable=False, server_default="mdns"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_summary", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_network_scan_runs_user_created_at", "network_scan_runs", ["requested_by_user_id", "created_at"])
    op.create_index("ix_network_scan_runs_status_created_at", "network_scan_runs", ["status", "created_at"])

    op.create_table(
        "network_scan_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("scan_run_id", sa.BigInteger(), sa.ForeignKey("network_scan_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False, server_default="http"),
        sa.Column("service_type", sa.String(length=160), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("state", sa.String(length=40), nullable=False, server_default="discovered"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_network_scan_results_scan_run_id", "network_scan_results", ["scan_run_id"])
    op.create_index("ix_network_scan_results_host", "network_scan_results", ["host"])


def downgrade() -> None:
    op.drop_table("network_scan_results")
    op.drop_table("network_scan_runs")
    op.drop_table("printers")
