from __future__ import annotations

from backend.domains.printers.adapter_types import InvalidPrintFileError
from backend.domains.printers.models import Printer


def base_url(printer: Printer) -> str:
    return f"{printer.protocol}://{printer.host}:{printer.port}"


def validate_sliced_filename(filename: str) -> str:
    clean = filename.strip().replace("\\", "/").lstrip("/")
    if not clean or clean.endswith("/") or ".." in clean.split("/"):
        raise InvalidPrintFileError("Print file name must be a relative G-code file path")
    lower = clean.lower()
    if not (lower.endswith(".gcode") or lower.endswith(".gcode.gz")):
        raise InvalidPrintFileError("Only already-sliced .gcode or .gcode.gz files are supported")
    return clean


def float_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def string_or_none(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
