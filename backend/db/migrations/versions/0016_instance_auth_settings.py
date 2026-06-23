"""instance auth settings

Revision ID: 0016_instance_auth_settings
Revises: 0015_printer_scan_capabilities
Create Date: 2026-06-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016_instance_auth_settings"
down_revision = "0015_printer_scan_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instance_settings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("setting_key", sa.String(length=120), nullable=False),
        sa.Column("setting_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("setting_key", name="uq_instance_settings_setting_key"),
    )
    op.create_index("ix_instance_settings_setting_key", "instance_settings", ["setting_key"])


def downgrade() -> None:
    op.drop_table("instance_settings")
