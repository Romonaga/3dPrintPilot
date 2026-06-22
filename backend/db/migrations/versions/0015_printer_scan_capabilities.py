"""printer scan capability metadata

Revision ID: 0015_printer_scan_capabilities
Revises: 0014_source_project_scans
Create Date: 2026-06-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_printer_scan_capabilities"
down_revision = "0014_source_project_scans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "network_scan_results",
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column("network_scan_results", sa.Column("build_volume_x_mm", sa.Integer(), nullable=True))
    op.add_column("network_scan_results", sa.Column("build_volume_y_mm", sa.Integer(), nullable=True))
    op.add_column("network_scan_results", sa.Column("build_volume_z_mm", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("network_scan_results", "build_volume_z_mm")
    op.drop_column("network_scan_results", "build_volume_y_mm")
    op.drop_column("network_scan_results", "build_volume_x_mm")
    op.drop_column("network_scan_results", "capabilities")
