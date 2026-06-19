"""printer confirmation and adapters

Revision ID: 0008_printer_adapters
Revises: 0007_resource_jobs
Create Date: 2026-06-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_printer_adapters"
down_revision = "0007_resource_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("printers", sa.Column("adapter_type", sa.String(length=80), nullable=True))
    op.add_column("printers", sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("printers", sa.Column("credential_secret_name", sa.String(length=120), nullable=True))
    op.add_column("printers", sa.Column("last_status", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("printers", sa.Column("last_status_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("network_scan_results", sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))


def downgrade() -> None:
    op.drop_column("network_scan_results", "evidence")
    op.drop_column("printers", "last_status_at")
    op.drop_column("printers", "last_status")
    op.drop_column("printers", "credential_secret_name")
    op.drop_column("printers", "capabilities")
    op.drop_column("printers", "adapter_type")
