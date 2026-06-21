from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.domains.ai.models import AiCostReconciliationRun, AiUsageEvent
from backend.domains.compatibility.models import CompatibilityCheck, CompatibilityCheckItem
from backend.domains.models.models import Model, ModelFile, ModelGeometry
from backend.domains.printers.models import NetworkScanResult, NetworkScanRun, Printer
from backend.domains.resources.models import BackgroundJob, ResourceSample
from backend.domains.settings.models import ProviderSecret
from backend.domains.site_scanning.models import ModelSiteAdapter, ModelSiteScanResult, ModelSiteScanRun, SiteAuthProfile
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/operations", tags=["operations"])


EXPORT_MODELS = (
    Printer,
    NetworkScanRun,
    NetworkScanResult,
    ModelSiteAdapter,
    ModelSiteScanRun,
    ModelSiteScanResult,
    Model,
    ModelFile,
    ModelGeometry,
    CompatibilityCheck,
    CompatibilityCheckItem,
    AiUsageEvent,
    AiCostReconciliationRun,
    ResourceSample,
    BackgroundJob,
)


@router.get("/backup.json")
def export_backup(
    _user=Depends(require_roles("admin")),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "format": "3dprintpilot.operations.backup",
        "security": {
            "provider_secrets": "redacted; only provider, name, last_four, and timestamps are exported",
            "site_auth_profiles": "redacted; only site, auth mode, label, last_four, and timestamps are exported",
            "restore": "restore by importing into matching schema after reconfiguring provider and site auth secrets manually",
        },
        "tables": {},
    }
    for model in EXPORT_MODELS:
        payload["tables"][model.__tablename__] = [
            _row_to_dict(row)
            for row in session.scalars(select(model).order_by(*model.__table__.primary_key.columns)).all()
        ]
    payload["tables"]["provider_secrets"] = [
        {
            "id": secret.id,
            "provider": secret.provider,
            "secret_name": secret.secret_name,
            "configured": True,
            "last_four": secret.last_four,
            "created_at": _serialize(secret.created_at),
            "updated_at": _serialize(secret.updated_at),
        }
        for secret in session.scalars(select(ProviderSecret).order_by(ProviderSecret.id)).all()
    ]
    payload["tables"]["site_auth_profiles"] = []
    if inspect(session.bind).has_table(SiteAuthProfile.__tablename__):
        payload["tables"]["site_auth_profiles"] = [
            {
                "id": profile.id,
                "site_key": profile.site_key,
                "auth_mode": profile.auth_mode,
                "label": profile.label,
                "header_name": profile.header_name,
                "configured": profile.encrypted_value is not None,
                "last_four": profile.last_four,
                "enabled": profile.enabled,
                "created_at": _serialize(profile.created_at),
                "updated_at": _serialize(profile.updated_at),
            }
            for profile in session.scalars(select(SiteAuthProfile).order_by(SiteAuthProfile.id)).all()
        ]
    return JSONResponse(
        payload,
        headers={"Content-Disposition": 'attachment; filename="3dprintpilot-backup.json"'},
    )


def _row_to_dict(row) -> dict[str, Any]:
    return {
        column.name: _serialize(getattr(row, column.name))
        for column in row.__table__.columns
    }


def _serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value
