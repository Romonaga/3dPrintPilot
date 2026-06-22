"""source project scan persistence

Revision ID: 0014_source_project_scans
Revises: 0013_source_site_auth_registry
Create Date: 2026-06-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_source_project_scans"
down_revision = "0013_source_site_auth_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_project_scans",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("site_key", sa.String(length=80), nullable=False),
        sa.Column("source_project_url", sa.Text(), nullable=False),
        sa.Column("external_project_id", sa.String(length=160), nullable=False),
        sa.Column("project_title", sa.String(length=300), nullable=True),
        sa.Column("requested_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_project_scans_created_at", "source_project_scans", ["created_at"])
    op.create_index("ix_source_project_scans_site_project", "source_project_scans", ["site_key", "external_project_id"])
    op.create_index("ix_source_project_scans_source_project_url", "source_project_scans", ["source_project_url"])
    op.create_table(
        "source_project_scan_files",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("scan_id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", sa.String(length=160), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=40), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("source_file_url", sa.Text(), nullable=False),
        sa.Column("supported_model_file", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_created_at", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["source_project_scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_project_scan_files_file_id", "source_project_scan_files", ["file_id"])
    op.create_index("ix_source_project_scan_files_scan_id", "source_project_scan_files", ["scan_id"])


def downgrade() -> None:
    op.drop_index("ix_source_project_scan_files_scan_id", table_name="source_project_scan_files")
    op.drop_index("ix_source_project_scan_files_file_id", table_name="source_project_scan_files")
    op.drop_table("source_project_scan_files")
    op.drop_index("ix_source_project_scans_source_project_url", table_name="source_project_scans")
    op.drop_index("ix_source_project_scans_site_project", table_name="source_project_scans")
    op.drop_index("ix_source_project_scans_created_at", table_name="source_project_scans")
    op.drop_table("source_project_scans")
