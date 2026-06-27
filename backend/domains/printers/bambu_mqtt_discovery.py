from __future__ import annotations

import socket
import ssl
from collections.abc import Callable

from backend.domains.printers.entities import DiscoveredPrinter


def probe_bambu_mqtt_port(
    host: str,
    port: int,
    timeout_seconds: float,
    mqtt_probe: Callable[[str, int, float], str],
) -> DiscoveredPrinter | None:
    mqtt_state = mqtt_probe(host, port, timeout_seconds)
    if mqtt_state != "mqtt":
        return None
    return DiscoveredPrinter(
        name=f"Bambu Lab MQTT broker at {host}:{port}",
        host=host,
        port=port,
        protocol="mqtts",
        service_type="mqtt_probe:bambu_mqtt",
        confidence=90,
        evidence=("MQTT over TLS CONNACK received; no publish/control commands sent",),
    )


def probe_mqtt_over_tls(host: str, port: int, timeout_seconds: float) -> str:
    context = ssl.create_default_context()
    # Bambu LAN MQTT discovery uses appliance certificates that often cannot be
    # host-verified during unauthenticated read-only discovery. This exception
    # is intentionally scoped to the MQTT handshake probe, not HTTP probing.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds) as raw_socket:
            raw_socket.settimeout(timeout_seconds)
            with context.wrap_socket(raw_socket, server_hostname=host) as tls_socket:
                tls_socket.settimeout(timeout_seconds)
                tls_socket.sendall(_mqtt_connect_packet())
                response = tls_socket.recv(4)
                if response and response[0] == 0x20:
                    return "mqtt"
                return "tls"
    except (OSError, ssl.SSLError, TimeoutError):
        return "tcp"


def _mqtt_connect_packet() -> bytes:
    client_id = b"3dprintpilot-scan"
    variable_header = b"\x00\x04MQTT\x04\x02\x00\x0a"
    payload = len(client_id).to_bytes(2, "big") + client_id
    remaining_length = len(variable_header) + len(payload)
    return b"\x10" + _mqtt_remaining_length(remaining_length) + variable_header + payload


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
