from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.core.config import get_settings
from backend.db.base import Base
from backend.domains.ai.models import AiCostReconciliationRun, AiUsageEvent
from backend.domains.compatibility.models import CompatibilityCheck, CompatibilityCheckItem
from backend.domains.models.models import Model, ModelFile, ModelFilePayload, ModelGeometry
from backend.domains.printers.models import NetworkScanResult, NetworkScanRun, Printer
from backend.domains.resources.models import BackgroundJob, ResourceSample
from backend.domains.settings.models import ProviderSecret
from backend.domains.site_scanning.models import ModelSiteAdapter, ModelSiteScanResult, ModelSiteScanRun, SiteAuthProfile
from backend.domains.users.models import User, UserSession

_ = (
    AiCostReconciliationRun,
    AiUsageEvent,
    CompatibilityCheck,
    CompatibilityCheckItem,
    Model,
    ModelFile,
    ModelFilePayload,
    ModelGeometry,
    ModelSiteAdapter,
    ModelSiteScanResult,
    ModelSiteScanRun,
    SiteAuthProfile,
    NetworkScanResult,
    NetworkScanRun,
    Printer,
    BackgroundJob,
    ResourceSample,
    ProviderSecret,
    User,
    UserSession,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_settings().database_url
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
