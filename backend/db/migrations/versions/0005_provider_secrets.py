"""encrypted provider secrets

Revision ID: 0005_provider_secrets
Revises: 0004_network_scan_metrics
Create Date: 2026-06-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_provider_secrets"
down_revision = "0004_network_scan_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_secrets",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("secret_name", sa.String(length=80), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("encryption_key_id", sa.String(length=64), nullable=False),
        sa.Column("secret_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("last_four", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("provider", "secret_name", name="uq_provider_secrets_provider_secret_name"),
    )
    op.create_index("ix_provider_secrets_provider", "provider_secrets", ["provider"])


def downgrade() -> None:
    op.drop_table("provider_secrets")
