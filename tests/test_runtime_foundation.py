from __future__ import annotations

import logging

from backend.core.config import Settings
from backend.core.logging import configure_logging


def test_settings_exposes_default_log_level():
    settings = Settings()

    assert settings.log_level == "INFO"


def test_configure_logging_accepts_unknown_level_name():
    configure_logging("not-a-real-level")

    assert logging.getLogger().getEffectiveLevel() in {logging.INFO, logging.WARNING}
