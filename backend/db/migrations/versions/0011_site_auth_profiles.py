"""site auth profiles

Revision ID: 0011_site_auth_profiles
Revises: 0010_printer_identity
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_site_auth_profiles"
down_revision = "0010_printer_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_auth_profiles",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("site_key", sa.String(length=80), nullable=False),
        sa.Column("auth_mode", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=True),
        sa.Column("header_name", sa.String(length=120), nullable=True),
        sa.Column("encrypted_value", sa.Text(), nullable=True),
        sa.Column("encryption_key_id", sa.String(length=64), nullable=True),
        sa.Column("secret_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("last_four", sa.String(length=8), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("site_key", name="uq_site_auth_profiles_site_key"),
    )
    op.create_index("ix_site_auth_profiles_site_key", "site_auth_profiles", ["site_key"])
    op.create_index("ix_site_auth_profiles_auth_mode", "site_auth_profiles", ["auth_mode"])


def downgrade() -> None:
    op.drop_table("site_auth_profiles")
