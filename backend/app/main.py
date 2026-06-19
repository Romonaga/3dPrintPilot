from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.domains.ai.routes import router as ai_router
from backend.domains.compatibility.routes import router as compatibility_router
from backend.domains.health.routes import router as health_router
from backend.domains.printers.routes import router as printers_router
from backend.domains.resources.routes import router as resources_router
from backend.domains.settings.routes import router as settings_router
from backend.domains.site_scanning.routes import router as site_scanning_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(printers_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(resources_router, prefix="/api")
    app.include_router(ai_router, prefix="/api")
    app.include_router(compatibility_router, prefix="/api")
    app.include_router(site_scanning_router, prefix="/api")
    return app


app = create_app()
