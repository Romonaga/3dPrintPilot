"""model uploads and geometry

Revision ID: 0009_model_uploads
Revises: 0008_printer_adapters
Create Date: 2026-06-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_model_uploads"
down_revision = "0008_printer_adapters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "models",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_models_status_created_at", "models", ["status", "created_at"])
    op.create_index("ix_models_created_by_created_at", "models", ["created_by_user_id", "created_at"])
    op.create_table(
        "model_files",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("model_id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=160), nullable=True),
        sa.Column("file_format", sa.String(length=20), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_status", sa.String(length=40), nullable=False),
        sa.Column("analysis_status", sa.String(length=40), nullable=False),
        sa.Column("analysis_job_id", sa.BigInteger(), nullable=True),
        sa.Column("analysis_warnings", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("raw_metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["background_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_model_files_model_id", "model_files", ["model_id"])
    op.create_index("ix_model_files_analysis_status_created_at", "model_files", ["analysis_status", "created_at"])
    op.create_table(
        "model_geometry",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("model_file_id", sa.BigInteger(), nullable=False),
        sa.Column("units", sa.String(length=40), nullable=False),
        sa.Column("size_x_mm", sa.Float(), nullable=True),
        sa.Column("size_y_mm", sa.Float(), nullable=True),
        sa.Column("size_z_mm", sa.Float(), nullable=True),
        sa.Column("min_x_mm", sa.Float(), nullable=True),
        sa.Column("min_y_mm", sa.Float(), nullable=True),
        sa.Column("min_z_mm", sa.Float(), nullable=True),
        sa.Column("max_x_mm", sa.Float(), nullable=True),
        sa.Column("max_y_mm", sa.Float(), nullable=True),
        sa.Column("max_z_mm", sa.Float(), nullable=True),
        sa.Column("volume_mm3", sa.Float(), nullable=True),
        sa.Column("triangle_count", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("raw_summary", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["model_file_id"], ["model_files.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("model_file_id", name="uq_model_geometry_model_file_id"),
    )
    op.create_index("ix_model_geometry_triangle_count", "model_geometry", ["triangle_count"])


def downgrade() -> None:
    op.drop_index("ix_model_geometry_triangle_count", table_name="model_geometry")
    op.drop_table("model_geometry")
    op.drop_index("ix_model_files_analysis_status_created_at", table_name="model_files")
    op.drop_index("ix_model_files_model_id", table_name="model_files")
    op.drop_table("model_files")
    op.drop_index("ix_models_created_by_created_at", table_name="models")
    op.drop_index("ix_models_status_created_at", table_name="models")
    op.drop_table("models")
