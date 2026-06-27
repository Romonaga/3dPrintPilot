"""slicer artifact persistence

Revision ID: 0017_slicer_artifacts
Revises: 0016_instance_auth_settings
Create Date: 2026-06-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0017_slicer_artifacts"
down_revision = "0016_instance_auth_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slicer_artifacts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("model_file_id", sa.BigInteger(), nullable=False),
        sa.Column("printer_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("output_filename", sa.String(length=255), nullable=False),
        sa.Column("output_format", sa.String(length=40), nullable=False),
        sa.Column("content_type", sa.String(length=160), nullable=True),
        sa.Column("slicer_name", sa.String(length=120), nullable=False),
        sa.Column("slicer_version", sa.String(length=80), nullable=True),
        sa.Column("profile_name", sa.String(length=160), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("settings_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="stored"),
        sa.Column("compression", sa.String(length=20), nullable=False),
        sa.Column("compressed_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("original_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("compressed_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("original_sha256", sa.String(length=64), nullable=False),
        sa.Column("compressed_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_file_id"], ["model_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["printer_id"], ["printers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_slicer_artifacts_model_file_id", "slicer_artifacts", ["model_file_id"])
    op.create_index("ix_slicer_artifacts_printer_id_created_at", "slicer_artifacts", ["printer_id", "created_at"])
    op.create_index("ix_slicer_artifacts_settings_hash", "slicer_artifacts", ["settings_hash"])


def downgrade() -> None:
    op.drop_index("ix_slicer_artifacts_settings_hash", table_name="slicer_artifacts")
    op.drop_index("ix_slicer_artifacts_printer_id_created_at", table_name="slicer_artifacts")
    op.drop_index("ix_slicer_artifacts_model_file_id", table_name="slicer_artifacts")
    op.drop_table("slicer_artifacts")
