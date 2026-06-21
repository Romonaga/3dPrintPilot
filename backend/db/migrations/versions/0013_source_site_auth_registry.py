"""source site auth registry metadata

Revision ID: 0013_source_site_auth_registry
Revises: 0012_model_file_payloads
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_source_site_auth_registry"
down_revision = "0012_model_file_payloads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_site_adapters", sa.Column("base_url", sa.Text(), nullable=True))
    op.add_column("model_site_adapters", sa.Column("login_url", sa.Text(), nullable=True))
    op.add_column(
        "model_site_adapters",
        sa.Column("auth_capabilities", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column("site_auth_profiles", sa.Column("account_identifier", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("site_auth_profiles", "account_identifier")
    op.drop_column("model_site_adapters", "auth_capabilities")
    op.drop_column("model_site_adapters", "login_url")
    op.drop_column("model_site_adapters", "base_url")
