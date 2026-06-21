from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from backend.domains.printers.models import Printer


@dataclass(frozen=True)
class PrinterStatus:
    adapter_type: str
    state: str
    capabilities: dict[str, Any]
    raw_status: dict[str, Any]
    observed_at: datetime


@dataclass(frozen=True)
class MoonrakerFile:
    path: str
    size: int | None
    modified: float | None
    permissions: str | None


@dataclass(frozen=True)
class MoonrakerJobStatus:
    state: str
    filename: str | None
    progress: float | None
    message: str | None
    raw_status: dict[str, Any]
    observed_at: datetime


@dataclass(frozen=True)
class MoonrakerActionResult:
    action: str
    accepted: bool
    raw_response: Any


class UnsupportedPrinterControlError(ValueError):
    pass


class InvalidPrintFileError(ValueError):
    pass


def infer_adapter_type(service_type: str | None, printer_type: str | None = None) -> str | None:
    haystack = f"{service_type or ''} {printer_type or ''}".lower()
    if "octoprint" in haystack:
        return "octoprint"
    if any(marker in haystack for marker in ("moonraker", "klipper", "mainsail", "fluidd", "snapmaker", "creality")):
        return "moonraker"
    return None


def capabilities_for_service_type(service_type: str | None) -> dict[str, Any]:
    adapter_type = infer_adapter_type(service_type)
    if adapter_type == "octoprint":
        return {
            "adapter": "octoprint",
            "read_only_status": True,
            "safe_endpoints": ["/api/version", "/api/printer"],
            "control_enabled": False,
        }
    if adapter_type == "moonraker":
        return {
            "adapter": "moonraker",
            "read_only_status": True,
            "safe_endpoints": [
                "/server/info",
                "/printer/info",
                "/printer/objects/list",
                "/printer/objects/query",
                "/server/files/list",
                "/server/files/upload",
                "/printer/print/start",
                "/printer/print/pause",
                "/printer/print/resume",
                "/printer/print/cancel",
            ],
            "control_enabled": True,
            "file_management": True,
            "job_control": True,
            "allowed_file_roots": ["gcodes"],
            "allowed_file_extensions": [".gcode", ".gcode.gz"],
            "allowed_job_actions": ["start", "pause", "resume", "cancel"],
            "raw_gcode_console": False,
        }
    return {"adapter": "unknown", "read_only_status": False, "control_enabled": False}


def fetch_read_only_status(printer: Printer, api_key: str | None = None, timeout_seconds: float = 2.0) -> PrinterStatus:
    adapter_type = printer.adapter_type or infer_adapter_type(None, printer.printer_type)
    if adapter_type == "octoprint":
        return _fetch_octoprint_status(printer, api_key=api_key, timeout_seconds=timeout_seconds)
    if adapter_type == "moonraker":
        return _fetch_moonraker_status(printer, timeout_seconds=timeout_seconds)
    return PrinterStatus(
        adapter_type=adapter_type or "unknown",
        state="unsupported",
        capabilities=printer.capabilities or capabilities_for_service_type(printer.printer_type),
        raw_status={"error": "No read-only adapter is available for this printer"},
        observed_at=datetime.now(UTC),
    )


def parse_octoprint_status(version_payload: dict[str, Any], printer_payload: dict[str, Any] | None = None) -> PrinterStatus:
    state = (printer_payload or {}).get("state", {}).get("text") or "unknown"
    capabilities = {
        "adapter": "octoprint",
        "read_only_status": True,
        "server": version_payload.get("server"),
        "api": version_payload.get("api"),
        "control_enabled": False,
    }
    return PrinterStatus(
        adapter_type="octoprint",
        state=str(state).lower().replace(" ", "_"),
        capabilities=capabilities,
        raw_status={"version": version_payload, "printer": printer_payload or {}},
        observed_at=datetime.now(UTC),
    )


def parse_moonraker_status(server_payload: dict[str, Any], printer_payload: dict[str, Any] | None = None) -> PrinterStatus:
    result = server_payload.get("result", server_payload)
    printer_result = (printer_payload or {}).get("result", printer_payload or {})
    klippy_state = result.get("klippy_state") or printer_result.get("state") or "unknown"
    components = result.get("components") or []
    capabilities = {
        "adapter": "moonraker",
        "read_only_status": True,
        "moonraker_version": result.get("software_version"),
        "components": components,
        "control_enabled": False,
    }
    return PrinterStatus(
        adapter_type="moonraker",
        state=str(klippy_state).lower(),
        capabilities=capabilities,
        raw_status={"server": server_payload, "printer": printer_payload or {}},
        observed_at=datetime.now(UTC),
    )


def _fetch_octoprint_status(printer: Printer, api_key: str | None, timeout_seconds: float) -> PrinterStatus:
    headers = {"X-Api-Key": api_key} if api_key else {}
    base_url = _base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        version = client.get(f"{base_url}/api/version", headers=headers).json()
        printer_payload = client.get(f"{base_url}/api/printer", headers=headers).json()
    return parse_octoprint_status(version, printer_payload)


def _fetch_moonraker_status(printer: Printer, timeout_seconds: float) -> PrinterStatus:
    base_url = _base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        server = client.get(f"{base_url}/server/info").json()
        printer_payload = client.get(f"{base_url}/printer/info").json()
    return parse_moonraker_status(server, printer_payload)


def fetch_moonraker_job_status(printer: Printer, timeout_seconds: float = 2.0) -> MoonrakerJobStatus:
    _require_moonraker_control(printer)
    base_url = _base_url(printer)
    query = "print_stats&virtual_sdcard&display_status&extruder&heater_bed"
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.get(f"{base_url}/printer/objects/query?{query}").json()
    return parse_moonraker_job_status(payload)


def parse_moonraker_job_status(payload: dict[str, Any]) -> MoonrakerJobStatus:
    result = payload.get("result", payload)
    status = result.get("status", result) if isinstance(result, dict) else {}
    print_stats = status.get("print_stats", {}) if isinstance(status, dict) else {}
    virtual_sdcard = status.get("virtual_sdcard", {}) if isinstance(status, dict) else {}
    display_status = status.get("display_status", {}) if isinstance(status, dict) else {}
    state = str(print_stats.get("state") or "unknown").lower()
    progress = _float_or_none(virtual_sdcard.get("progress") or display_status.get("progress"))
    return MoonrakerJobStatus(
        state=state,
        filename=_string_or_none(print_stats.get("filename") or virtual_sdcard.get("file_path")),
        progress=progress,
        message=_string_or_none(print_stats.get("message")),
        raw_status=payload,
        observed_at=datetime.now(UTC),
    )


def list_moonraker_files(printer: Printer, timeout_seconds: float = 5.0) -> list[MoonrakerFile]:
    _require_moonraker_control(printer)
    base_url = _base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.get(f"{base_url}/server/files/list", params={"root": "gcodes"}).json()
    files = payload.get("result", payload) if isinstance(payload, dict) else payload
    if not isinstance(files, list):
        return []
    return [
        MoonrakerFile(
            path=str(item.get("path") or item.get("filename") or ""),
            size=_int_or_none(item.get("size")),
            modified=_float_or_none(item.get("modified")),
            permissions=_string_or_none(item.get("permissions")),
        )
        for item in files
        if isinstance(item, dict) and (item.get("path") or item.get("filename"))
    ]


def upload_moonraker_file(
    printer: Printer,
    filename: str,
    content: bytes,
    content_type: str | None = None,
    timeout_seconds: float = 30.0,
) -> MoonrakerActionResult:
    _require_moonraker_control(printer)
    safe_filename = _validate_sliced_filename(filename)
    base_url = _base_url(printer)
    files = {
        "file": (
            safe_filename,
            content,
            content_type or "application/octet-stream",
        )
    }
    data = {"root": "gcodes", "print": "false"}
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.post(f"{base_url}/server/files/upload", files=files, data=data).json()
    return MoonrakerActionResult(action="upload", accepted=True, raw_response=payload)


def start_moonraker_print(printer: Printer, filename: str, timeout_seconds: float = 5.0) -> MoonrakerActionResult:
    _require_moonraker_control(printer)
    safe_filename = _validate_sliced_filename(filename)
    base_url = _base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.post(f"{base_url}/printer/print/start?filename={quote(safe_filename)}").json()
    return MoonrakerActionResult(action="start", accepted=True, raw_response=payload)


def pause_moonraker_print(printer: Printer, timeout_seconds: float = 5.0) -> MoonrakerActionResult:
    return _moonraker_print_action(printer, "pause", timeout_seconds)


def resume_moonraker_print(printer: Printer, timeout_seconds: float = 5.0) -> MoonrakerActionResult:
    return _moonraker_print_action(printer, "resume", timeout_seconds)


def cancel_moonraker_print(printer: Printer, timeout_seconds: float = 5.0) -> MoonrakerActionResult:
    return _moonraker_print_action(printer, "cancel", timeout_seconds)


def _base_url(printer: Printer) -> str:
    return f"{printer.protocol}://{printer.host}:{printer.port}"


def _require_moonraker_control(printer: Printer) -> None:
    adapter_type = printer.adapter_type or infer_adapter_type(None, printer.printer_type)
    stored_capabilities = printer.capabilities or {}
    inferred_capabilities = capabilities_for_service_type(printer.printer_type)
    control_enabled = bool(inferred_capabilities.get("control_enabled") or stored_capabilities.get("control_enabled"))
    if adapter_type != "moonraker" or not control_enabled:
        raise UnsupportedPrinterControlError("Moonraker file and job controls are not available for this printer")


def _moonraker_print_action(printer: Printer, action: str, timeout_seconds: float) -> MoonrakerActionResult:
    _require_moonraker_control(printer)
    base_url = _base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.post(f"{base_url}/printer/print/{action}").json()
    return MoonrakerActionResult(action=action, accepted=True, raw_response=payload)


def _validate_sliced_filename(filename: str) -> str:
    clean = filename.strip().replace("\\", "/").lstrip("/")
    if not clean or clean.endswith("/") or ".." in clean.split("/"):
        raise InvalidPrintFileError("Print file name must be a relative G-code file path")
    lower = clean.lower()
    if not (lower.endswith(".gcode") or lower.endswith(".gcode.gz")):
        raise InvalidPrintFileError("Only already-sliced .gcode or .gcode.gz files are supported")
    return clean


def _float_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
