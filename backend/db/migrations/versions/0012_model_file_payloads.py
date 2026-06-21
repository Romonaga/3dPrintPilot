"""model file payload storage

Revision ID: 0012_model_file_payloads
Revises: 0011_site_auth_profiles
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_model_file_payloads"
down_revision = "0011_site_auth_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_file_payloads",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("model_file_id", sa.BigInteger(), nullable=False),
        sa.Column("source_project_url", sa.Text(), nullable=False),
        sa.Column("source_file_url", sa.Text(), nullable=False),
        sa.Column("compression", sa.String(length=20), nullable=False),
        sa.Column("compressed_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("original_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("compressed_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("original_sha256", sa.String(length=64), nullable=False),
        sa.Column("compressed_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["model_file_id"], ["model_files.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("model_file_id", name="uq_model_file_payloads_model_file_id"),
    )
    op.create_index("ix_model_file_payloads_original_sha256", "model_file_payloads", ["original_sha256"])


def downgrade() -> None:
    op.drop_index("ix_model_file_payloads_original_sha256", table_name="model_file_payloads")
    op.drop_table("model_file_payloads")
