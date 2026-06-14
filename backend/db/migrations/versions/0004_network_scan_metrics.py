"""network scan metric columns

Revision ID: 0004_network_scan_metrics
Revises: 0003_printers
Create Date: 2026-06-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_network_scan_metrics"
down_revision = "0003_printers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "network_scan_runs",
        sa.Column("scanned_host_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "network_scan_runs",
        sa.Column("probe_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("network_scan_runs", "probe_count")
    op.drop_column("network_scan_runs", "scanned_host_count")
