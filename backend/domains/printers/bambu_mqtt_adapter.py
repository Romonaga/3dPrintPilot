from __future__ import annotations

from datetime import UTC, datetime
import json
import socket
import ssl
from typing import Any

from backend.domains.printers.adapter_capabilities import capabilities_for_service_type
from backend.domains.printers.adapter_types import PrinterStatus
from backend.domains.printers.adapter_utils import float_or_none, string_or_none
from backend.domains.printers.models import Printer

DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS = 5.0


def fetch_bambu_mqtt_status(
    printer: Printer,
    access_code: str | None = None,
    timeout_seconds: float = DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS,
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
    timeout_seconds: float = DEFAULT_PRINTER_TELEMETRY_TIMEOUT_SECONDS,
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
    progress = float_or_none(print_payload.get("mc_percent") or print_payload.get("progress"))
    job = {
        "state": state,
        "filename": print_payload.get("gcode_file") or print_payload.get("subtask_name"),
        "progress": progress,
        "remaining_minutes": float_or_none(print_payload.get("mc_remaining_time")),
    }
    temperatures = {
        "nozzle_current_c": float_or_none(print_payload.get("nozzle_temper")),
        "nozzle_target_c": float_or_none(print_payload.get("nozzle_target_temper")),
        "bed_current_c": float_or_none(print_payload.get("bed_temper")),
        "bed_target_c": float_or_none(print_payload.get("bed_target_temper")),
        "chamber_current_c": float_or_none(print_payload.get("chamber_temper")),
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
    active_tray = string_or_none(ams_payload.get("tray_now") or ams_payload.get("tray_tar"))
    trays: list[dict[str, Any]] = []
    for unit in ams_payload.get("ams", []) if isinstance(ams_payload.get("ams"), list) else []:
        if not isinstance(unit, dict):
            continue
        for tray in unit.get("tray", []) if isinstance(unit.get("tray"), list) else []:
            if not isinstance(tray, dict):
                continue
            tray_id = string_or_none(tray.get("id"))
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
