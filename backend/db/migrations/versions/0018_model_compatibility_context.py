"""model compatibility check context

Revision ID: 0018_model_compatibility_context
Revises: 0017_slicer_artifacts
Create Date: 2026-06-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0018_model_compatibility_context"
down_revision = "0017_slicer_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("compatibility_checks", sa.Column("model_id", sa.BigInteger(), nullable=True))
    op.add_column("compatibility_checks", sa.Column("model_file_id", sa.BigInteger(), nullable=True))
    op.alter_column("compatibility_checks", "scan_result_id", existing_type=sa.BigInteger(), nullable=True)
    op.create_foreign_key(
        "fk_compatibility_checks_model_id_models",
        "compatibility_checks",
        "models",
        ["model_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_compatibility_checks_model_file_id_model_files",
        "compatibility_checks",
        "model_files",
        ["model_file_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_compatibility_checks_model_id_created_at", "compatibility_checks", ["model_id", "created_at"])
    op.create_index("ix_compatibility_checks_model_file_id", "compatibility_checks", ["model_file_id"])


def downgrade() -> None:
    op.drop_index("ix_compatibility_checks_model_file_id", table_name="compatibility_checks")
    op.drop_index("ix_compatibility_checks_model_id_created_at", table_name="compatibility_checks")
    op.drop_constraint("fk_compatibility_checks_model_file_id_model_files", "compatibility_checks", type_="foreignkey")
    op.drop_constraint("fk_compatibility_checks_model_id_models", "compatibility_checks", type_="foreignkey")
    op.alter_column("compatibility_checks", "scan_result_id", existing_type=sa.BigInteger(), nullable=False)
    op.drop_column("compatibility_checks", "model_file_id")
    op.drop_column("compatibility_checks", "model_id")
