from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class ProviderSecret(Base):
    __tablename__ = "provider_secrets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    secret_name: Mapped[str] = mapped_column(String(80), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    encryption_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    last_four: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "secret_name", name="uq_provider_secrets_provider_secret_name"),
        Index("ix_provider_secrets_provider", "provider"),
    )


class InstanceSetting(Base):
    __tablename__ = "instance_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    setting_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_instance_settings_setting_key", "setting_key"),)
