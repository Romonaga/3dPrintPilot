"""compatibility check persistence

Revision ID: 0006_compatibility_checks
Revises: 0005_provider_secrets
Create Date: 2026-06-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_compatibility_checks"
down_revision = "0005_provider_secrets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compatibility_checks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "scan_result_id",
            sa.BigInteger(),
            sa.ForeignKey("model_site_scan_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("printer_id", sa.BigInteger(), sa.ForeignKey("printers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="metadata_only"),
        sa.Column("confidence_label", sa.String(length=40), nullable=False, server_default="low"),
        sa.Column("model_title", sa.String(length=300), nullable=False),
        sa.Column("model_url", sa.Text(), nullable=False),
        sa.Column("printer_name", sa.String(length=160), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_requirements", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_compatibility_checks_scan_result_id", "compatibility_checks", ["scan_result_id"])
    op.create_index(
        "ix_compatibility_checks_printer_id_created_at",
        "compatibility_checks",
        ["printer_id", "created_at"],
    )
    op.create_index("ix_compatibility_checks_status_created_at", "compatibility_checks", ["status", "created_at"])

    op.create_table(
        "compatibility_check_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "check_id",
            sa.BigInteger(),
            sa.ForeignKey("compatibility_checks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_compatibility_check_items_check_id", "compatibility_check_items", ["check_id"])


def downgrade() -> None:
    op.drop_table("compatibility_check_items")
    op.drop_table("compatibility_checks")
