"""printer discovery identity

Revision ID: 0010_printer_identity
Revises: 0009_model_uploads
Create Date: 2026-06-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_printer_identity"
down_revision = "0009_model_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("printers", sa.Column("identity_key", sa.String(length=255), nullable=True))
    op.create_index("uq_printers_identity_key", "printers", ["identity_key"], unique=True)
    op.add_column("network_scan_results", sa.Column("identity_key", sa.String(length=255), nullable=True))
    op.add_column("network_scan_results", sa.Column("matched_printer_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_network_scan_results_matched_printer_id",
        "network_scan_results",
        "printers",
        ["matched_printer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_network_scan_results_identity_key", "network_scan_results", ["identity_key"])
    op.create_index(
        "ix_network_scan_results_matched_printer_id",
        "network_scan_results",
        ["matched_printer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_network_scan_results_matched_printer_id", table_name="network_scan_results")
    op.drop_index("ix_network_scan_results_identity_key", table_name="network_scan_results")
    op.drop_constraint(
        "fk_network_scan_results_matched_printer_id",
        "network_scan_results",
        type_="foreignkey",
    )
    op.drop_column("network_scan_results", "matched_printer_id")
    op.drop_column("network_scan_results", "identity_key")
    op.drop_index("uq_printers_identity_key", table_name="printers")
    op.drop_column("printers", "identity_key")
