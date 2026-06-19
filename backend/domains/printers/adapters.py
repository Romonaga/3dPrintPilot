from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.domains.printers.models import Printer


@dataclass(frozen=True)
class PrinterStatus:
    adapter_type: str
    state: str
    capabilities: dict[str, Any]
    raw_status: dict[str, Any]
    observed_at: datetime


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
            "safe_endpoints": ["/server/info", "/printer/info", "/printer/objects/list"],
            "control_enabled": False,
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


def _base_url(printer: Printer) -> str:
    return f"{printer.protocol}://{printer.host}:{printer.port}"
