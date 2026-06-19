from __future__ import annotations

import logging

from backend.core.config import Settings
from backend.core import database
from backend.core.logging import configure_logging


def test_settings_exposes_default_log_level():
    settings = Settings()

    assert settings.log_level == "INFO"


def test_configure_logging_accepts_unknown_level_name():
    configure_logging("not-a-real-level")

    assert logging.getLogger().getEffectiveLevel() in {logging.INFO, logging.WARNING}


def test_database_engine_uses_explicit_pool_bounds(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)
    monkeypatch.setattr(database, "get_settings", lambda: Settings())

    database.create_database_engine()

    assert captured["kwargs"]["pool_pre_ping"] is True
    assert captured["kwargs"]["pool_timeout"] == 30
    assert captured["kwargs"]["pool_recycle"] == 1800
    assert captured["kwargs"]["pool_size"] == 5
    assert captured["kwargs"]["max_overflow"] == 10
