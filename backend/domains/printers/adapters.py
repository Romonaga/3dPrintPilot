from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from backend.domains.printers.adapter_capabilities import capabilities_for_service_type, infer_adapter_type
from backend.domains.printers.adapter_types import (
    ExtensionMethodNotAllowedError,
    InvalidPrintFileError,
    MoonrakerActionResult,
    MoonrakerCapabilityDiagnostics,
    MoonrakerExtensionResult,
    MoonrakerFile,
    MoonrakerJobStatus,
    MoonrakerTemperature,
    MoonrakerToolheadTelemetry,
    PrinterStatus,
    UnsupportedPrinterControlError,
)
from backend.domains.printers.adapter_utils import base_url
from backend.domains.printers import bambu_mqtt_adapter
from backend.domains.printers.bambu_mqtt_adapter import fetch_bambu_mqtt_report, parse_bambu_mqtt_status
from backend.domains.printers.models import Printer
from backend.domains.printers.moonraker_adapter import (
    cancel_moonraker_print,
    fetch_moonraker_capability_diagnostics,
    list_moonraker_files,
    parse_moonraker_capability_diagnostics,
    parse_moonraker_job_status,
    pause_moonraker_print,
    request_moonraker_extension,
    resume_moonraker_print,
    start_moonraker_print,
    upload_moonraker_file,
)

__all__ = [
    "BambuMqttPrinterEngine",
    "ExtensionMethodNotAllowedError",
    "InvalidPrintFileError",
    "MoonrakerActionResult",
    "MoonrakerCapabilityDiagnostics",
    "MoonrakerExtensionResult",
    "MoonrakerFile",
    "MoonrakerJobStatus",
    "MoonrakerPrinterEngine",
    "MoonrakerTemperature",
    "MoonrakerToolheadTelemetry",
    "PrinterEngine",
    "PrinterStatus",
    "UnsupportedPrinterControlError",
    "cancel_moonraker_print",
    "capabilities_for_service_type",
    "engine_catalog",
    "engine_for_printer",
    "fetch_bambu_mqtt_status",
    "fetch_bambu_mqtt_report",
    "fetch_moonraker_capability_diagnostics",
    "fetch_moonraker_job_status",
    "fetch_read_only_status",
    "infer_adapter_type",
    "list_moonraker_files",
    "parse_bambu_mqtt_status",
    "parse_moonraker_capability_diagnostics",
    "parse_moonraker_job_status",
    "parse_moonraker_status",
    "parse_octoprint_status",
    "pause_moonraker_print",
    "refresh_engine_catalog",
    "request_moonraker_extension",
    "resume_moonraker_print",
    "start_moonraker_print",
    "upload_moonraker_file",
]

DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS = 5.0


class PrinterEngine:
    engine_id = "base"
    display_name = "Base printer engine"
    description = "Base printer engine contract."

    def supports(self, printer: Printer) -> bool:
        _ = printer
        return False

    def fetch_job_status(
        self,
        printer: Printer,
        timeout_seconds: float = DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS,
    ) -> MoonrakerJobStatus:
        _ = printer, timeout_seconds
        raise UnsupportedPrinterControlError("Job telemetry is not available for this printer")


class MoonrakerPrinterEngine(PrinterEngine):
    engine_id = "moonraker"
    display_name = "Moonraker"
    description = "Moonraker/Klipper-compatible printer telemetry and control engine."

    def supports(self, printer: Printer) -> bool:
        adapter_type = printer.adapter_type or infer_adapter_type(None, printer.printer_type)
        return adapter_type == self.engine_id

    def fetch_job_status(
        self,
        printer: Printer,
        timeout_seconds: float = DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS,
    ) -> MoonrakerJobStatus:
        from backend.domains.printers.moonraker_adapter import MoonrakerTelemetryEngine, require_moonraker_control

        require_moonraker_control(printer)
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            payload = MoonrakerTelemetryEngine(client, base_url(printer)).fetch_job_status_payload()
        return parse_moonraker_job_status(payload, capabilities=printer.capabilities or {})


class BambuMqttPrinterEngine(PrinterEngine):
    engine_id = "bambu_mqtt"
    display_name = "Bambu LAN MQTT"
    description = "Bambu LAN/Developer mode read-only MQTT telemetry engine."

    def supports(self, printer: Printer) -> bool:
        adapter_type = printer.adapter_type or infer_adapter_type(None, printer.printer_type)
        return adapter_type == self.engine_id


PRINTER_ENGINES: tuple[PrinterEngine, ...] = (MoonrakerPrinterEngine(), BambuMqttPrinterEngine())


def refresh_engine_catalog() -> tuple[PrinterEngine, ...]:
    return PRINTER_ENGINES


def engine_catalog() -> list[dict[str, Any]]:
    return [
        {
            "engine_id": engine.engine_id,
            "display_name": engine.display_name,
            "description": engine.description,
            "capabilities": capabilities_for_service_type(engine.engine_id),
        }
        for engine in refresh_engine_catalog()
    ]


def engine_for_printer(printer: Printer) -> PrinterEngine | None:
    for engine in refresh_engine_catalog():
        if engine.supports(printer):
            return engine
    return None


def fetch_read_only_status(
    printer: Printer,
    api_key: str | None = None,
    timeout_seconds: float = DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS,
) -> PrinterStatus:
    adapter_type = printer.adapter_type or infer_adapter_type(None, printer.printer_type)
    try:
        if adapter_type == "octoprint":
            return _fetch_octoprint_status(printer, api_key=api_key, timeout_seconds=timeout_seconds)
        if adapter_type == "moonraker":
            return _fetch_moonraker_status(printer, timeout_seconds=timeout_seconds)
        if adapter_type == "bambu_mqtt":
            return fetch_bambu_mqtt_status(printer, access_code=api_key, timeout_seconds=timeout_seconds)
    except (httpx.HTTPError, ValueError) as exc:
        return _telemetry_unavailable_status(
            printer,
            adapter_type=adapter_type,
            reason="timeout" if isinstance(exc, httpx.TimeoutException) else "unreachable",
            timeout_seconds=timeout_seconds,
        )
    return PrinterStatus(
        adapter_type=adapter_type or "unknown",
        state="unsupported",
        capabilities=printer.capabilities or capabilities_for_service_type(printer.printer_type),
        raw_status={"error": "No read-only adapter is available for this printer"},
        observed_at=datetime.now(UTC),
    )


def fetch_bambu_mqtt_status(
    printer: Printer,
    access_code: str | None = None,
    timeout_seconds: float = DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS,
) -> PrinterStatus:
    original_fetch_report = bambu_mqtt_adapter.fetch_bambu_mqtt_report
    bambu_mqtt_adapter.fetch_bambu_mqtt_report = fetch_bambu_mqtt_report
    try:
        return bambu_mqtt_adapter.fetch_bambu_mqtt_status(
            printer,
            access_code=access_code,
            timeout_seconds=timeout_seconds,
        )
    finally:
        bambu_mqtt_adapter.fetch_bambu_mqtt_report = original_fetch_report


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
    url = base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        version = client.get(f"{url}/api/version", headers=headers).json()
        printer_payload = client.get(f"{url}/api/printer", headers=headers).json()
    return parse_octoprint_status(version, printer_payload)


def _fetch_moonraker_status(printer: Printer, timeout_seconds: float) -> PrinterStatus:
    url = base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        server = client.get(f"{url}/server/info").json()
        printer_payload = client.get(f"{url}/printer/info").json()
    return parse_moonraker_status(server, printer_payload)


def _telemetry_unavailable_status(
    printer: Printer,
    adapter_type: str | None,
    reason: str,
    timeout_seconds: float,
) -> PrinterStatus:
    resolved_adapter = adapter_type or "unknown"
    capabilities = {
        **capabilities_for_service_type(resolved_adapter),
        **(printer.capabilities or {}),
    }
    return PrinterStatus(
        adapter_type=resolved_adapter,
        state="telemetry_unavailable",
        capabilities=capabilities,
        raw_status={
            "source": resolved_adapter,
            "reason": reason,
            "message": f"Printer telemetry timed out after {timeout_seconds:g} seconds"
            if reason == "timeout"
            else "Printer telemetry is unavailable",
            "timeout_seconds": timeout_seconds,
        },
        observed_at=datetime.now(UTC),
    )


def fetch_moonraker_job_status(
    printer: Printer,
    timeout_seconds: float = DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS,
) -> MoonrakerJobStatus:
    engine = engine_for_printer(printer)
    if not isinstance(engine, MoonrakerPrinterEngine):
        raise UnsupportedPrinterControlError("Moonraker file and job controls are not available for this printer")
    return engine.fetch_job_status(printer, timeout_seconds=timeout_seconds)
