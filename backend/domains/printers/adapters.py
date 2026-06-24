from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import socket
import ssl
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
    bed_temperature: "MoonrakerTemperature | None" = None
    toolheads: tuple["MoonrakerToolheadTelemetry", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MoonrakerTemperature:
    current_c: float | None
    target_c: float | None
    power: float | None = None


@dataclass(frozen=True)
class MoonrakerToolheadTelemetry:
    name: str
    label: str
    index: int
    current_temperature: MoonrakerTemperature | None
    color: str | None = None
    color_source: str | None = None
    material: str | None = None
    material_source: str | None = None
    vendor: str | None = None
    subtype: str | None = None


@dataclass(frozen=True)
class MoonrakerActionResult:
    action: str
    accepted: bool
    raw_response: Any


@dataclass(frozen=True)
class MoonrakerExtensionResult:
    agent: str
    method: str
    accepted: bool
    raw_response: Any


@dataclass(frozen=True)
class MoonrakerCapabilityDiagnostics:
    adapter_type: str
    extension_agents_available: bool
    extension_agents: tuple[dict[str, Any], ...]
    spoolman_available: bool
    spoolman_status: dict[str, Any] | None
    probe_errors: dict[str, str]
    observed_at: datetime


@dataclass(frozen=True)
class SnapmakerU1FilamentSlot:
    index: int
    color: str | None = None
    material: str | None = None
    vendor: str | None = None
    subtype: str | None = None


@dataclass(frozen=True)
class SpoolmanFilamentMetadata:
    color: str | None = None
    material: str | None = None
    vendor: str | None = None


class UnsupportedPrinterControlError(ValueError):
    pass


class InvalidPrintFileError(ValueError):
    pass


class ExtensionMethodNotAllowedError(ValueError):
    pass


class PrinterEngine:
    engine_id = "base"
    display_name = "Base printer engine"
    description = "Base printer engine contract."

    def supports(self, printer: Printer) -> bool:
        _ = printer
        return False

    def fetch_job_status(self, printer: Printer, timeout_seconds: float = 2.0) -> MoonrakerJobStatus:
        _ = printer, timeout_seconds
        raise UnsupportedPrinterControlError("Job telemetry is not available for this printer")


class MoonrakerPrinterEngine(PrinterEngine):
    engine_id = "moonraker"
    display_name = "Moonraker"
    description = "Moonraker/Klipper-compatible printer telemetry and control engine."

    def supports(self, printer: Printer) -> bool:
        adapter_type = printer.adapter_type or infer_adapter_type(None, printer.printer_type)
        return adapter_type == self.engine_id

    def fetch_job_status(self, printer: Printer, timeout_seconds: float = 2.0) -> MoonrakerJobStatus:
        _require_moonraker_control(printer)
        base_url = _base_url(printer)
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            payload = MoonrakerTelemetryEngine(client, base_url).fetch_job_status_payload()
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


def infer_adapter_type(service_type: str | None, printer_type: str | None = None) -> str | None:
    haystack = f"{service_type or ''} {printer_type or ''}".lower()
    if "octoprint" in haystack:
        return "octoprint"
    if "bambu_mqtt" in haystack or ("bambu" in haystack and "mqtt" in haystack):
        return "bambu_mqtt"
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
            "telemetry_source_priority": [
                "moonraker_object",
                "vendor_object",
                "spoolman",
                "extension_agent",
                "saved_capabilities",
            ],
        }
    if adapter_type == "bambu_mqtt":
        return {
            "adapter": "bambu_mqtt",
            "read_only_status": True,
            "control_enabled": False,
            "protocol": "mqtts",
            "default_port": 8883,
            "credential_required": True,
            "required_credentials": ["lan_access_code", "device_id"],
            "safe_topics": ["device/{device_id}/report", "device/{device_id}/request"],
            "safe_methods": ["pushing.pushall"],
            "pushall_min_interval_seconds": 300,
            "raw_gcode_console": False,
            "local_mode_tradeoff": "LAN or Developer mode may limit Bambu Handy or cloud workflows on some firmware.",
            "telemetry_source_priority": [
                "bambu_mqtt_report",
                "saved_capabilities",
            ],
        }
    return {"adapter": "unknown", "read_only_status": False, "control_enabled": False}


def fetch_read_only_status(printer: Printer, api_key: str | None = None, timeout_seconds: float = 2.0) -> PrinterStatus:
    adapter_type = printer.adapter_type or infer_adapter_type(None, printer.printer_type)
    if adapter_type == "octoprint":
        return _fetch_octoprint_status(printer, api_key=api_key, timeout_seconds=timeout_seconds)
    if adapter_type == "moonraker":
        return _fetch_moonraker_status(printer, timeout_seconds=timeout_seconds)
    if adapter_type == "bambu_mqtt":
        return _fetch_bambu_mqtt_status(printer, access_code=api_key, timeout_seconds=timeout_seconds)
    return PrinterStatus(
        adapter_type=adapter_type or "unknown",
        state="unsupported",
        capabilities=printer.capabilities or capabilities_for_service_type(printer.printer_type),
        raw_status={"error": "No read-only adapter is available for this printer"},
        observed_at=datetime.now(UTC),
    )


def _fetch_bambu_mqtt_status(
    printer: Printer,
    access_code: str | None = None,
    timeout_seconds: float = 2.0,
) -> PrinterStatus:
    capabilities = capabilities_for_service_type("bambu_mqtt") | (printer.capabilities or {})
    capabilities["control_enabled"] = False
    capabilities["raw_gcode_console"] = False
    credential_configured = getattr(printer, "credential_secret_name", None) is not None
    device_id = _bambu_device_id(printer, capabilities)
    if not credential_configured:
        state = "credentials_required"
        message = "Bambu LAN MQTT telemetry requires the printer LAN access code before status can be read."
    elif not device_id:
        state = "device_id_required"
        message = "Bambu LAN MQTT telemetry requires a device ID or serial topic before status can be read."
    else:
        try:
            report = fetch_bambu_mqtt_report(
                printer,
                device_id=device_id,
                access_code=access_code,
                timeout_seconds=timeout_seconds,
            )
        except BambuMqttTelemetryError as exc:
            return PrinterStatus(
                adapter_type="bambu_mqtt",
                state="telemetry_unavailable",
                capabilities=capabilities,
                raw_status={
                    "source": "bambu_mqtt",
                    "message": str(exc),
                    "credential_configured": credential_configured,
                    "device_id_configured": True,
                    "control_enabled": False,
                },
                observed_at=datetime.now(UTC),
            )
        return parse_bambu_mqtt_status(report, capabilities=capabilities)
    return PrinterStatus(
        adapter_type="bambu_mqtt",
        state=state,
        capabilities=capabilities,
        raw_status={
            "source": "bambu_mqtt_engine_foundation",
            "message": message,
            "credential_configured": credential_configured,
            "device_id_configured": bool(device_id),
            "control_enabled": False,
        },
        observed_at=datetime.now(UTC),
    )


def _bambu_device_id(printer: Printer, capabilities: dict[str, Any]) -> str | None:
    for key in ("device_id", "serial", "printer_serial"):
        value = capabilities.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    identity_key = getattr(printer, "identity_key", None)
    if isinstance(identity_key, str) and identity_key.startswith("bambu:"):
        return identity_key.split(":", 1)[1].strip() or None
    return None


class BambuMqttTelemetryError(RuntimeError):
    pass


def fetch_bambu_mqtt_report(
    printer: Printer,
    device_id: str,
    access_code: str | None,
    timeout_seconds: float = 2.0,
) -> dict[str, Any]:
    if not access_code:
        raise BambuMqttTelemetryError("Bambu LAN access code is not configured")
    return BambuMqttClient(
        host=printer.host,
        port=int(printer.port or 8883),
        device_id=device_id,
        access_code=access_code,
        timeout_seconds=timeout_seconds,
    ).fetch_report()


class BambuMqttClient:
    def __init__(
        self,
        host: str,
        port: int,
        device_id: str,
        access_code: str,
        timeout_seconds: float,
    ) -> None:
        self.host = host
        self.port = port
        self.device_id = device_id
        self.access_code = access_code
        self.timeout_seconds = timeout_seconds

    def fetch_report(self) -> dict[str, Any]:
        report_topic = f"device/{self.device_id}/report"
        request_topic = f"device/{self.device_id}/request"
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout_seconds) as raw_socket:
                raw_socket.settimeout(self.timeout_seconds)
                with context.wrap_socket(raw_socket, server_hostname=self.host) as mqtt_socket:
                    mqtt_socket.settimeout(self.timeout_seconds)
                    mqtt_socket.sendall(_mqtt_connect_packet("3dprintpilot", "bblp", self.access_code))
                    _require_mqtt_connack(mqtt_socket)
                    mqtt_socket.sendall(_mqtt_subscribe_packet(1, report_topic))
                    _require_mqtt_suback(mqtt_socket)
                    mqtt_socket.sendall(
                        _mqtt_publish_packet(
                            request_topic,
                            {"pushing": {"sequence_id": "0", "command": "pushall"}},
                        )
                    )
                    return _read_bambu_mqtt_report(mqtt_socket, report_topic)
        except BambuMqttTelemetryError:
            raise
        except (OSError, ssl.SSLError, TimeoutError, json.JSONDecodeError) as exc:
            raise BambuMqttTelemetryError("Bambu LAN MQTT telemetry is unavailable") from exc


def parse_bambu_mqtt_status(payload: dict[str, Any], capabilities: dict[str, Any] | None = None) -> PrinterStatus:
    print_payload = payload.get("print") if isinstance(payload.get("print"), dict) else payload
    normalized = _normalize_bambu_print_payload(print_payload)
    return PrinterStatus(
        adapter_type="bambu_mqtt",
        state=normalized["state"],
        capabilities={
            **capabilities_for_service_type("bambu_mqtt"),
            **(capabilities or {}),
            "control_enabled": False,
            "raw_gcode_console": False,
        },
        raw_status={
            "source": "bambu_mqtt",
            "job": normalized["job"],
            "temperatures": normalized["temperatures"],
            "ams": normalized["ams"],
            "errors": normalized["errors"],
            "raw_report": payload,
            "control_enabled": False,
        },
        observed_at=datetime.now(UTC),
    )


def _normalize_bambu_print_payload(print_payload: dict[str, Any]) -> dict[str, Any]:
    state = _normalize_bambu_state(print_payload.get("gcode_state") or print_payload.get("state"))
    progress = _float_or_none(print_payload.get("mc_percent") or print_payload.get("progress"))
    job = {
        "state": state,
        "filename": print_payload.get("gcode_file") or print_payload.get("subtask_name"),
        "progress": progress,
        "remaining_minutes": _float_or_none(print_payload.get("mc_remaining_time")),
    }
    temperatures = {
        "nozzle_current_c": _float_or_none(print_payload.get("nozzle_temper")),
        "nozzle_target_c": _float_or_none(print_payload.get("nozzle_target_temper")),
        "bed_current_c": _float_or_none(print_payload.get("bed_temper")),
        "bed_target_c": _float_or_none(print_payload.get("bed_target_temper")),
        "chamber_current_c": _float_or_none(print_payload.get("chamber_temper")),
    }
    ams = _normalize_bambu_ams(print_payload.get("ams") if isinstance(print_payload.get("ams"), dict) else {})
    errors = {
        "hms": print_payload.get("hms") if isinstance(print_payload.get("hms"), list) else [],
        "print_error": print_payload.get("print_error"),
    }
    return {"state": state, "job": job, "temperatures": temperatures, "ams": ams, "errors": errors}


def _normalize_bambu_state(value: Any) -> str:
    state = str(value or "online").strip().lower()
    return {
        "running": "printing",
        "prepare": "printing",
        "pause": "paused",
        "paused": "paused",
        "idle": "idle",
        "finish": "complete",
        "finished": "complete",
        "failed": "error",
    }.get(state, state or "online")


def _normalize_bambu_ams(ams_payload: dict[str, Any]) -> dict[str, Any]:
    active_tray = _string_or_none(ams_payload.get("tray_now") or ams_payload.get("tray_tar"))
    trays: list[dict[str, Any]] = []
    for unit in ams_payload.get("ams", []) if isinstance(ams_payload.get("ams"), list) else []:
        if not isinstance(unit, dict):
            continue
        for tray in unit.get("tray", []) if isinstance(unit.get("tray"), list) else []:
            if not isinstance(tray, dict):
                continue
            tray_id = _string_or_none(tray.get("id"))
            trays.append(
                {
                    "id": tray_id,
                    "active": tray_id is not None and tray_id == active_tray,
                    "color": _normalize_bambu_color(tray.get("tray_color")),
                    "material": tray.get("tray_type"),
                    "subtype": tray.get("tray_sub_brands") or tray.get("tray_info_idx"),
                }
            )
    return {"active_tray": active_tray, "trays": trays}


def _normalize_bambu_color(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    clean = value.strip().lstrip("#")
    if len(clean) >= 6:
        return f"#{clean[:6].lower()}"
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def _mqtt_connect_packet(client_id: str, username: str, password: str) -> bytes:
    variable_header = _mqtt_string("MQTT") + b"\x04\xc2\x00<"
    payload = _mqtt_string(client_id) + _mqtt_string(username) + _mqtt_string(password)
    return b"\x10" + _mqtt_remaining_length(len(variable_header) + len(payload)) + variable_header + payload


def _mqtt_subscribe_packet(packet_id: int, topic: str) -> bytes:
    payload = packet_id.to_bytes(2, "big") + _mqtt_string(topic) + b"\x00"
    return b"\x82" + _mqtt_remaining_length(len(payload)) + payload


def _mqtt_publish_packet(topic: str, payload: dict[str, Any]) -> bytes:
    body = _mqtt_string(topic) + json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return b"\x30" + _mqtt_remaining_length(len(body)) + body


def _mqtt_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(2, "big") + encoded


def _mqtt_remaining_length(value: int) -> bytes:
    encoded = bytearray()
    while True:
        byte = value % 128
        value //= 128
        if value > 0:
            byte |= 128
        encoded.append(byte)
        if value == 0:
            return bytes(encoded)


def _mqtt_read_packet(mqtt_socket) -> tuple[int, bytes]:
    header = _recv_exact(mqtt_socket, 1)
    remaining = 0
    multiplier = 1
    while True:
        encoded = _recv_exact(mqtt_socket, 1)[0]
        remaining += (encoded & 127) * multiplier
        if encoded & 128 == 0:
            break
        multiplier *= 128
        if multiplier > 128 * 128 * 128:
            raise BambuMqttTelemetryError("Invalid MQTT remaining length")
    return header[0], _recv_exact(mqtt_socket, remaining)


def _recv_exact(mqtt_socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = mqtt_socket.recv(length - len(chunks))
        if not chunk:
            raise BambuMqttTelemetryError("Bambu LAN MQTT connection closed")
        chunks.extend(chunk)
    return bytes(chunks)


def _require_mqtt_connack(mqtt_socket) -> None:
    packet_type, payload = _mqtt_read_packet(mqtt_socket)
    if packet_type != 0x20 or len(payload) < 2 or payload[1] != 0:
        raise BambuMqttTelemetryError("Bambu LAN MQTT authentication failed")


def _require_mqtt_suback(mqtt_socket) -> None:
    packet_type, payload = _mqtt_read_packet(mqtt_socket)
    if packet_type != 0x90 or not payload or payload[-1] == 0x80:
        raise BambuMqttTelemetryError("Bambu LAN MQTT report subscription failed")


def _read_bambu_mqtt_report(mqtt_socket, expected_topic: str) -> dict[str, Any]:
    for _ in range(8):
        packet_type, payload = _mqtt_read_packet(mqtt_socket)
        if packet_type & 0xF0 != 0x30 or len(payload) < 2:
            continue
        topic_length = int.from_bytes(payload[:2], "big")
        topic = payload[2 : 2 + topic_length].decode("utf-8")
        if topic != expected_topic:
            continue
        report_payload = payload[2 + topic_length :].decode("utf-8")
        report = json.loads(report_payload)
        if isinstance(report, dict):
            return report
    raise BambuMqttTelemetryError("Bambu LAN MQTT report was not received")


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
    engine = engine_for_printer(printer)
    if not isinstance(engine, MoonrakerPrinterEngine):
        raise UnsupportedPrinterControlError("Moonraker file and job controls are not available for this printer")
    return engine.fetch_job_status(printer, timeout_seconds=timeout_seconds)


def fetch_moonraker_capability_diagnostics(
    printer: Printer,
    timeout_seconds: float = 2.0,
) -> MoonrakerCapabilityDiagnostics:
    _require_moonraker_adapter(printer)
    base_url = _base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        extensions_payload, extensions_error = _optional_moonraker_json(client, f"{base_url}/server/extensions/list")
        spoolman_payload, spoolman_error = _optional_moonraker_json(client, f"{base_url}/server/spoolman/status")
    errors = {}
    if extensions_error:
        errors["extensions"] = extensions_error
    if spoolman_error:
        errors["spoolman"] = spoolman_error
    return parse_moonraker_capability_diagnostics(
        extensions_payload=extensions_payload,
        spoolman_payload=spoolman_payload,
        probe_errors=errors,
    )


def request_moonraker_extension(
    printer: Printer,
    agent: str,
    method: str,
    arguments: dict[str, Any] | None = None,
    timeout_seconds: float = 5.0,
) -> MoonrakerExtensionResult:
    _require_moonraker_adapter(printer)
    if not _moonraker_extension_method_allowed(printer.capabilities or {}, agent, method):
        raise ExtensionMethodNotAllowedError("Moonraker extension method is not allowlisted for this printer")
    base_url = _base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.post(
            f"{base_url}/server/extensions/request",
            json={"agent": agent, "method": method, "arguments": arguments or {}},
        ).json()
    return MoonrakerExtensionResult(agent=agent, method=method, accepted=True, raw_response=payload)


def parse_moonraker_capability_diagnostics(
    extensions_payload: dict[str, Any] | None = None,
    spoolman_payload: dict[str, Any] | None = None,
    probe_errors: dict[str, str] | None = None,
) -> MoonrakerCapabilityDiagnostics:
    errors = dict(probe_errors or {})
    extension_agents = _moonraker_extension_agents(extensions_payload)
    spoolman_status = _moonraker_spoolman_status(spoolman_payload)
    return MoonrakerCapabilityDiagnostics(
        adapter_type="moonraker",
        extension_agents_available=bool(extension_agents),
        extension_agents=extension_agents,
        spoolman_available=spoolman_status is not None and "spoolman" not in errors,
        spoolman_status=spoolman_status,
        probe_errors=errors,
        observed_at=datetime.now(UTC),
    )


class MoonrakerTelemetryEngine:
    def __init__(self, client: httpx.Client, base_url: str) -> None:
        self.client = client
        self.base_url = base_url

    def fetch_job_status_payload(self) -> dict[str, Any]:
        object_names = self._available_object_names()
        extruder_names = _moonraker_extruder_names_from_object_names(object_names) or ("extruder",)
        snapmaker_objects = tuple(
            name
            for name in (
                "filament_detect",
                "filament_feed left",
                "filament_feed right",
                "gcode_macro _FILAMENT_FEED_VARIABLE",
            )
            if name in object_names
        )
        query_objects = [
            "print_stats",
            "virtual_sdcard",
            "display_status",
            "heater_bed",
            "configfile",
            *extruder_names,
            *snapmaker_objects,
        ]
        query = "&".join(quote(name, safe="") for name in dict.fromkeys(query_objects))
        payload = self.client.get(f"{self.base_url}/printer/objects/query?{query}").json()
        self._attach_spoolman_payload(payload)
        return payload

    def _available_object_names(self) -> tuple[str, ...]:
        try:
            payload = self.client.get(f"{self.base_url}/printer/objects/list").json()
        except httpx.HTTPError:
            return ()
        return _moonraker_object_names_from_object_list(payload)

    def _attach_spoolman_payload(self, payload: dict[str, Any]) -> None:
        spoolman_payload, spoolman_error = _optional_moonraker_json(self.client, f"{self.base_url}/server/spoolman/status")
        if spoolman_error or not isinstance(spoolman_payload, dict):
            return
        status = _moonraker_query_status(payload)
        spoolman_status = _moonraker_spoolman_status(spoolman_payload)
        if not isinstance(status, dict) or spoolman_status is None:
            return
        status["spoolman"] = spoolman_status
        spool_id = _int_or_none(spoolman_status.get("spool_id"))
        if spool_id is None:
            return
        active_spool_payload, active_spool_error = _optional_moonraker_post_json(
            self.client,
            f"{self.base_url}/server/spoolman/proxy",
            {
                "use_v2_response": True,
                "request_method": "GET",
                "path": f"/v1/spool/{spool_id}",
            },
        )
        if active_spool_error is None and isinstance(active_spool_payload, dict):
            status["spoolman_active_spool"] = active_spool_payload


def parse_moonraker_job_status(payload: dict[str, Any], capabilities: dict[str, Any] | None = None) -> MoonrakerJobStatus:
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
        bed_temperature=_moonraker_temperature(status.get("heater_bed") if isinstance(status, dict) else None),
        toolheads=_moonraker_toolhead_telemetry(status, capabilities or {}),
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
    _require_moonraker_adapter(printer)
    stored_capabilities = printer.capabilities or {}
    inferred_capabilities = capabilities_for_service_type(printer.printer_type)
    control_enabled = bool(inferred_capabilities.get("control_enabled") or stored_capabilities.get("control_enabled"))
    if not control_enabled:
        raise UnsupportedPrinterControlError("Moonraker file and job controls are not available for this printer")


def _require_moonraker_adapter(printer: Printer) -> None:
    adapter_type = printer.adapter_type or infer_adapter_type(None, printer.printer_type)
    if adapter_type != "moonraker":
        raise UnsupportedPrinterControlError("Moonraker file and job controls are not available for this printer")


def _moonraker_print_action(printer: Printer, action: str, timeout_seconds: float) -> MoonrakerActionResult:
    _require_moonraker_control(printer)
    base_url = _base_url(printer)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        payload = client.post(f"{base_url}/printer/print/{action}").json()
    return MoonrakerActionResult(action=action, accepted=True, raw_response=payload)


def _moonraker_extruder_names_from_object_list(payload: dict[str, Any]) -> tuple[str, ...]:
    return _moonraker_extruder_names_from_object_names(_moonraker_object_names_from_object_list(payload))


def _moonraker_object_names_from_object_list(payload: dict[str, Any]) -> tuple[str, ...]:
    result = payload.get("result", payload)
    objects = result.get("objects", result) if isinstance(result, dict) else result
    if not isinstance(objects, list):
        return ()
    return tuple(name for name in objects if isinstance(name, str))


def _moonraker_extruder_names_from_object_names(objects: tuple[str, ...]) -> tuple[str, ...]:
    names = [name for name in objects if _is_moonraker_extruder_name(name)]
    return tuple(sorted(set(names), key=_moonraker_extruder_sort_key))


def _optional_moonraker_json(client: httpx.Client, url: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = client.get(url)
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None, "unreachable"
    if response.status_code == 404:
        return payload if isinstance(payload, dict) else None, "not_configured"
    if response.status_code >= 400:
        return payload if isinstance(payload, dict) else None, f"http_{response.status_code}"
    return payload if isinstance(payload, dict) else None, None


def _optional_moonraker_post_json(client: httpx.Client, url: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = client.post(url, json=payload)
        response_payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None, "unreachable"
    if response.status_code == 404:
        return response_payload if isinstance(response_payload, dict) else None, "not_configured"
    if response.status_code >= 400:
        return response_payload if isinstance(response_payload, dict) else None, f"http_{response.status_code}"
    return response_payload if isinstance(response_payload, dict) else None, None


def _moonraker_query_status(payload: dict[str, Any]) -> dict[str, Any] | None:
    result = payload.get("result", payload)
    status = result.get("status", result) if isinstance(result, dict) else None
    return status if isinstance(status, dict) else None


def _moonraker_extension_agents(payload: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, dict):
        return ()
    result = payload.get("result", payload)
    agents = result.get("agents") if isinstance(result, dict) else None
    if not isinstance(agents, list):
        return ()
    return tuple(
        {
            "name": _string_or_none(agent.get("name")),
            "version": _string_or_none(agent.get("version")),
            "type": _string_or_none(agent.get("type")),
            "url": _string_or_none(agent.get("url")),
        }
        for agent in agents
        if isinstance(agent, dict) and _string_or_none(agent.get("name"))
    )


def _moonraker_spoolman_status(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    result = payload.get("result", payload)
    if not isinstance(result, dict) or "error" in result:
        return None
    return result


def _spoolman_filament_metadata(status: dict[str, Any]) -> SpoolmanFilamentMetadata | None:
    active_spool = status.get("spoolman_active_spool") if isinstance(status, dict) else None
    if not isinstance(active_spool, dict):
        return None
    response = active_spool.get("response", active_spool)
    if not isinstance(response, dict):
        return None
    filament = response.get("filament")
    if not isinstance(filament, dict):
        return None
    vendor = filament.get("vendor")
    return SpoolmanFilamentMetadata(
        color=_spoolman_color(filament),
        material=_string_or_none(filament.get("material")),
        vendor=_string_or_none(vendor.get("name")) if isinstance(vendor, dict) else _string_or_none(vendor),
    )


def _spoolman_color(filament: dict[str, Any]) -> str | None:
    color = _string_or_none(filament.get("color_hex"))
    if not color:
        return None
    normalized = color.lstrip("#").strip()
    if len(normalized) != 6:
        return None
    return f"#{normalized.lower()}"


def _moonraker_extension_method_allowed(capabilities: dict[str, Any], agent: str, method: str) -> bool:
    allowed_methods = capabilities.get("moonraker_extension_methods")
    if not isinstance(allowed_methods, list):
        return False
    for item in allowed_methods:
        if not isinstance(item, dict):
            continue
        if _string_or_none(item.get("agent")) == agent and _string_or_none(item.get("method")) == method:
            return True
    return False


def _moonraker_toolhead_telemetry(status: dict[str, Any], capabilities: dict[str, Any]) -> tuple[MoonrakerToolheadTelemetry, ...]:
    if not isinstance(status, dict):
        return ()
    configfile = status.get("configfile", {})
    settings = {}
    if isinstance(configfile, dict):
        settings = configfile.get("settings") or configfile.get("config") or {}
    if not isinstance(settings, dict):
        settings = {}
    capability_toolheads = capabilities.get("toolheads")
    capability_colors = _capability_tool_colors(capability_toolheads)
    snapmaker_slots = _snapmaker_u1_filament_slots(status)
    spoolman_metadata = _spoolman_filament_metadata(status)
    names = sorted(
        {key for key in status if _is_moonraker_extruder_name(key)} | {key for key in settings if _is_moonraker_extruder_name(key)},
        key=_moonraker_extruder_sort_key,
    )
    toolheads = []
    for name in names:
        index = _moonraker_extruder_index(name)
        payload = status.get(name) if isinstance(status.get(name), dict) else {}
        config = settings.get(name) if isinstance(settings.get(name), dict) else {}
        snapmaker_slot = snapmaker_slots.get(index)
        spoolman_slot = spoolman_metadata if len(names) == 1 else None
        color, color_source = _moonraker_toolhead_color(payload, config, snapmaker_slot, spoolman_slot, capability_colors.get(index))
        material = snapmaker_slot.material if snapmaker_slot else spoolman_slot.material if spoolman_slot else None
        material_source = "vendor_object" if snapmaker_slot and snapmaker_slot.material else "spoolman" if spoolman_slot and spoolman_slot.material else None
        vendor = snapmaker_slot.vendor if snapmaker_slot else spoolman_slot.vendor if spoolman_slot else None
        toolheads.append(
            MoonrakerToolheadTelemetry(
                name=name,
                label=f"T{index}",
                index=index,
                current_temperature=_moonraker_temperature(payload),
                color=color,
                color_source=color_source,
                material=material,
                material_source=material_source,
                vendor=vendor,
                subtype=snapmaker_slot.subtype if snapmaker_slot else None,
            )
        )
    return tuple(toolheads)


def _moonraker_temperature(payload: Any) -> MoonrakerTemperature | None:
    if not isinstance(payload, dict):
        return None
    current = _float_or_none(payload.get("temperature"))
    target = _float_or_none(payload.get("target"))
    power = _float_or_none(payload.get("power"))
    if current is None and target is None and power is None:
        return None
    return MoonrakerTemperature(current_c=current, target_c=target, power=power)


def _moonraker_color(payload: dict[str, Any], config: dict[str, Any], fallback: str | None = None) -> str | None:
    color, _source = _moonraker_color_with_source(payload, config, fallback)
    return color


def _moonraker_toolhead_color(
    payload: dict[str, Any],
    config: dict[str, Any],
    vendor_slot: SnapmakerU1FilamentSlot | None,
    spoolman_metadata: SpoolmanFilamentMetadata | None,
    capability_fallback: str | None,
) -> tuple[str | None, str | None]:
    color, source = _moonraker_color_with_source(payload, config)
    if color:
        return color, source
    if vendor_slot and vendor_slot.color:
        return vendor_slot.color, "vendor_object"
    if spoolman_metadata and spoolman_metadata.color:
        return spoolman_metadata.color, "spoolman"
    if capability_fallback:
        return capability_fallback, "saved_capabilities"
    return None, None


def _moonraker_color_with_source(
    payload: dict[str, Any],
    config: dict[str, Any],
    fallback: str | None = None,
) -> tuple[str | None, str | None]:
    for source in (payload, config):
        color = _color_from_mapping(source)
        if color:
            return color, "moonraker_object" if source is payload else "moonraker_config"
    if fallback:
        return fallback, "saved_capabilities"
    return None, None


def _color_from_mapping(source: dict[str, Any]) -> str | None:
    for key in ("filament_color", "material_color", "spool_color", "color", "colour"):
        color = _string_or_none(source.get(key))
        if color:
            return color
    for nested_key in ("filament", "material", "spool"):
        nested = source.get(nested_key)
        if isinstance(nested, dict):
            color = _color_from_mapping(nested)
            if color:
                return color
    return None


def _capability_tool_colors(toolheads: Any) -> dict[int, str]:
    if not isinstance(toolheads, list):
        return {}
    colors: dict[int, str] = {}
    for item in toolheads:
        if not isinstance(item, dict):
            continue
        index = _int_or_none(item.get("index"))
        color = _color_from_mapping(item)
        if index is not None and color:
            colors[index] = color
    return colors


def _snapmaker_u1_filament_slots(status: dict[str, Any]) -> dict[int, SnapmakerU1FilamentSlot]:
    filament_detect = status.get("filament_detect") if isinstance(status, dict) else None
    info_items = filament_detect.get("info") if isinstance(filament_detect, dict) else None
    if not isinstance(info_items, list):
        return {}
    slots: dict[int, SnapmakerU1FilamentSlot] = {}
    for index, item in enumerate(info_items):
        if not isinstance(item, dict) or _snapmaker_filament_is_empty(item):
            continue
        slots[index] = SnapmakerU1FilamentSlot(
            index=index,
            color=_snapmaker_color(item),
            material=_string_or_none(item.get("MAIN_TYPE")),
            vendor=_string_or_none(item.get("VENDOR")) or _string_or_none(item.get("MANUFACTURER")),
            subtype=_string_or_none(item.get("SUB_TYPE")),
        )
    return slots


def _snapmaker_filament_is_empty(item: dict[str, Any]) -> bool:
    material = (_string_or_none(item.get("MAIN_TYPE")) or "").upper()
    vendor = (_string_or_none(item.get("VENDOR")) or "").upper()
    manufacturer = (_string_or_none(item.get("MANUFACTURER")) or "").upper()
    return material in {"", "NONE"} and vendor in {"", "NONE"} and manufacturer in {"", "NONE"}


def _snapmaker_color(item: dict[str, Any]) -> str | None:
    for key in ("RGB_1", "ARGB_COLOR"):
        value = _int_or_none(item.get(key))
        if value is not None:
            return f"#{value & 0xFFFFFF:06x}"
    return None


def _is_moonraker_extruder_name(name: str) -> bool:
    return name == "extruder" or (name.startswith("extruder") and name[8:].isdigit())


def _moonraker_extruder_index(name: str) -> int:
    if name == "extruder":
        return 0
    return _int_or_none(name[8:]) or 0


def _moonraker_extruder_sort_key(name: str) -> tuple[int, str]:
    return (_moonraker_extruder_index(name), name)


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
