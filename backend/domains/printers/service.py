from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from functools import lru_cache
from ipaddress import IPv4Network, ip_network
import socket
import ssl
from time import monotonic, sleep
from urllib.parse import urljoin

import httpx
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from backend.domains.printers.entities import (
    DiscoveredPrinter,
    PrinterScanResult,
    PrinterScanStatus,
    PrinterScanSummary,
)

PRINTER_SERVICE_TYPES = (
    "_octoprint._tcp.local.",
    "_moonraker._tcp.local.",
    "_klipper._tcp.local.",
    "_mainsail._tcp.local.",
    "_fluidd._tcp.local.",
    "_prusalink._tcp.local.",
    "_bambulab._tcp.local.",
    "_bambu._tcp.local.",
    "_bblp._tcp.local.",
    "_snapmaker._tcp.local.",
    "_creality._tcp.local.",
    "_http._tcp.local.",
    "_ipp._tcp.local.",
)

DEFAULT_HTTP_PROBE_PORTS = (80, 443, 4408, 5000, 6000, 7125, 8000, 8080, 8081, 8883)
PREFERRED_HTTP_PROBE_PORTS = (7125, 8883, 4408, 8000, 8080, 80, 443, 5000, 6000, 8081)
MAX_HTTP_PROBE_PORTS = 10
MDNS_BRAND_MARKERS = {
    "bambu": ("Bambu Lab", "mdns:bambu", 86),
    "bblp": ("Bambu Lab", "mdns:bambu", 86),
    "creality": ("Creality", "mdns:creality", 80),
    "k2": ("Creality K2", "mdns:creality", 80),
    "snapmaker": ("Snapmaker", "mdns:snapmaker", 80),
    "u1": ("Snapmaker U1", "mdns:snapmaker", 76),
}


class _PrinterServiceListener(ServiceListener):
    def __init__(self) -> None:
        self.discovered: dict[tuple[str, int], DiscoveredPrinter] = {}

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        info = zeroconf.get_service_info(service_type, name)
        if info is None:
            return
        addresses = [address for address in info.parsed_scoped_addresses() if address]
        if not addresses:
            return
        metadata = _mdns_printer_metadata(service_type, name)
        if metadata is None:
            return
        host = addresses[0]
        protocol, service_label, confidence = metadata
        printer = DiscoveredPrinter(
            name=name.rstrip("."),
            host=host,
            port=info.port,
            protocol=protocol,
            service_type=service_label,
            confidence=confidence,
            evidence=(f"mDNS service {service_type} advertised {name}",),
        )
        self.discovered[(host, info.port)] = printer

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self.add_service(zeroconf, service_type, name)

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        return None


def scan_lan_for_printers(
    timeout_seconds: float = 8.0,
    scan_method: str = "combined",
    target_cidr: str | None = None,
    max_hosts: int = 254,
    ports: tuple[int, ...] | None = None,
    connect_timeout_seconds: float = 0.35,
) -> PrinterScanResult:
    scan_method = scan_method.lower()
    if scan_method not in {"mdns", "http_probe", "combined"}:
        raise ValueError("scan_method must be mdns, http_probe, or combined")
    started = monotonic()
    discovered: dict[tuple[str, int, str], DiscoveredPrinter] = {}
    scanned_host_count = 0
    probe_count = 0

    if scan_method in {"mdns", "combined"}:
        mdns_result = _scan_mdns(timeout_seconds=timeout_seconds)
        for printer in mdns_result.printers:
            discovered[(printer.host, printer.port, printer.service_type)] = printer
        scanned_host_count += mdns_result.summary.scanned_host_count
        probe_count += mdns_result.summary.probe_count

    if scan_method in {"http_probe", "combined"}:
        http_result = _scan_http_printers(
            target_cidr=target_cidr,
            max_hosts=max_hosts,
            ports=ports or DEFAULT_HTTP_PROBE_PORTS,
            connect_timeout_seconds=connect_timeout_seconds,
            scan_timeout_seconds=timeout_seconds,
        )
        for printer in http_result.printers:
            discovered[(printer.host, printer.port, printer.service_type)] = printer
        scanned_host_count += http_result.summary.scanned_host_count
        probe_count += http_result.summary.probe_count

    printers = _sort_discovered_printers(discovered.values())
    return PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=int((monotonic() - started) * 1000),
            discovered_count=len(printers),
            method=scan_method,
            scanned_host_count=scanned_host_count,
            probe_count=probe_count,
        ),
        printers=printers,
    )


def _scan_mdns(timeout_seconds: float = 3.0) -> PrinterScanResult:
    started = monotonic()
    listener = _PrinterServiceListener()
    zeroconf = Zeroconf()
    try:
        browsers = [ServiceBrowser(zeroconf, service_type, listener) for service_type in PRINTER_SERVICE_TYPES]
        _ = browsers
        while monotonic() - started < timeout_seconds:
            sleep(0.05)
    finally:
        zeroconf.close()

    printers = _sort_discovered_printers(listener.discovered.values())
    duration_ms = int((monotonic() - started) * 1000)
    return PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=duration_ms,
            discovered_count=len(printers),
            method="mdns",
            probe_count=len(PRINTER_SERVICE_TYPES),
        ),
        printers=printers,
    )


def _scan_http_printers(
    target_cidr: str | None,
    max_hosts: int,
    ports: tuple[int, ...],
    connect_timeout_seconds: float,
    scan_timeout_seconds: float | None = None,
) -> PrinterScanResult:
    started = monotonic()
    network = _resolve_probe_network(target_cidr)
    hosts = _limited_hosts(network, max_hosts=max_hosts)
    checked_ports = _prioritized_probe_ports(ports)
    discovered: dict[tuple[str, int], DiscoveredPrinter] = {}
    probe_count = len(hosts) * len(checked_ports)

    executor = ThreadPoolExecutor(max_workers=min(128, max(1, probe_count)))
    futures = [
        executor.submit(_probe_http_port, host, port, connect_timeout_seconds)
        for port in checked_ports
        for host in hosts
    ]
    try:
        completed_futures = as_completed(
            futures,
            timeout=max(scan_timeout_seconds, 0.1) if scan_timeout_seconds is not None else None,
        )
        for future in completed_futures:
            try:
                printer = future.result()
            except Exception:
                continue
            if printer is not None:
                discovered[(printer.host, printer.port)] = printer
    except FuturesTimeoutError:
        pass
    finally:
        for future in futures:
            if not future.done():
                future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    printers = _sort_discovered_printers(discovered.values())
    return PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=int((monotonic() - started) * 1000),
            discovered_count=len(printers),
            method="http_probe",
            scanned_host_count=len(hosts),
            probe_count=probe_count,
        ),
        printers=printers,
    )


def _probe_host_ports(host: str, ports: tuple[int, ...], timeout_seconds: float) -> tuple[DiscoveredPrinter, ...]:
    printers = []
    for port in ports:
        printer = _probe_http_port(host, port, timeout_seconds)
        if printer is not None:
            printers.append(printer)
    return tuple(printers)


def _probe_http_port(host: str, port: int, timeout_seconds: float) -> DiscoveredPrinter | None:
    if not _tcp_port_open(host, port, timeout_seconds):
        return None
    if port == 8883:
        return _probe_bambu_mqtt_port(host, port, timeout_seconds)
    scheme = "https" if port == 443 else "http"
    base_url = f"{scheme}://{host}:{port}"
    timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, verify=True) as client:
            for path, detector in _probe_paths(port):
                try:
                    response = client.get(urljoin(base_url, path))
                except httpx.HTTPError:
                    continue
                printer = detector(host, port, scheme, response)
                if printer is not None:
                    return printer
    except httpx.HTTPError:
        return None
    return None


def _probe_bambu_mqtt_port(host: str, port: int, timeout_seconds: float) -> DiscoveredPrinter | None:
    mqtt_state = _probe_mqtt_over_tls(host, port, timeout_seconds)
    if mqtt_state == "mqtt":
        return DiscoveredPrinter(
            name=f"Bambu Lab MQTT broker at {host}:{port}",
            host=host,
            port=port,
            protocol="mqtts",
            service_type="mqtt_probe:bambu_mqtt",
            confidence=90,
            evidence=("MQTT over TLS CONNACK received; no publish/control commands sent",),
        )
    return None


def _probe_mqtt_over_tls(host: str, port: int, timeout_seconds: float) -> str:
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


def _tcp_port_open(host: str, port: int, timeout_seconds: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _probe_paths(port: int):
    if port == 7125:
        return (("/server/info", _detect_moonraker), ("/printer/info", _detect_moonraker), ("/", _detect_generic_http))
    if port == 4408:
        return (("/", _detect_generic_http), ("/server/info", _detect_moonraker))
    return (
        ("/api/version", _detect_octoprint_or_prusalink),
        ("/server/info", _detect_moonraker),
        ("/rr_status?type=1", _detect_duet),
        ("/", _detect_generic_http),
    )


def _detect_octoprint_or_prusalink(host: str, port: int, scheme: str, response: httpx.Response) -> DiscoveredPrinter | None:
    text = response.text.lower()
    if response.status_code == 200 and "moonraker" in text:
        return _http_printer("Moonraker", host, port, scheme, "http_probe:moonraker", 92)
    if response.status_code == 200 and "octoprint" in text:
        return _http_printer("OctoPrint", host, port, scheme, "http_probe:octoprint", 92)
    if response.status_code in {200, 401} and ("prus" in text or "prusalink" in response.headers.get("server", "").lower()):
        return _http_printer("PrusaLink", host, port, scheme, "http_probe:prusalink", 88)
    return None


def _detect_moonraker(host: str, port: int, scheme: str, response: httpx.Response) -> DiscoveredPrinter | None:
    text = response.text.lower()
    if response.status_code == 200 and "snapmakercloud" in text:
        return _http_printer("Snapmaker U1 Moonraker", host, port, scheme, "http_probe:snapmaker_moonraker", 94)
    if response.status_code == 200 and "k2plus" in text:
        return _http_printer("Creality K2 Plus Moonraker", host, port, scheme, "http_probe:creality_moonraker", 94)
    if response.status_code == 200 and ("moonraker" in text or "klippy" in text or "klipper" in text):
        return _http_printer("Moonraker", host, port, scheme, "http_probe:moonraker", 92)
    return None


def _detect_duet(host: str, port: int, scheme: str, response: httpx.Response) -> DiscoveredPrinter | None:
    text = response.text.lower()
    if response.status_code == 200 and ("status" in text or "coords" in text) and ("seq" in text or "temps" in text):
        return _http_printer("Duet Web Control", host, port, scheme, "http_probe:duet", 82)
    return None


def _detect_generic_http(host: str, port: int, scheme: str, response: httpx.Response) -> DiscoveredPrinter | None:
    text = response.text.lower()
    server = response.headers.get("server", "").lower()
    markers = {
        "octoprint": ("OctoPrint", "http_probe:octoprint", 88),
        "creality": ("Creality", "http_probe:creality", 84),
        "creality k2": ("Creality K2", "http_probe:creality", 84),
        "k2plus": ("Creality K2 Plus", "http_probe:creality", 84),
        "moonraker": ("Moonraker", "http_probe:moonraker", 88),
        "klipper": ("Klipper/Moonraker", "http_probe:moonraker", 84),
        "mainsail": ("Mainsail/Klipper", "http_probe:moonraker", 82),
        "fluidd": ("Fluidd/Klipper", "http_probe:moonraker", 82),
        "prusalink": ("PrusaLink", "http_probe:prusalink", 84),
        "prusa link": ("PrusaLink", "http_probe:prusalink", 84),
        "duet": ("Duet Web Control", "http_probe:duet", 78),
        "bambu": ("Bambu Lab", "http_probe:bambu", 78),
        "snapmaker": ("Snapmaker", "http_probe:snapmaker", 78),
    }
    haystack = f"{server}\n{text}"
    for marker, (name, service_type, confidence) in markers.items():
        if marker in haystack:
            return _http_printer(name, host, port, scheme, service_type, confidence)
    return None


def _http_printer(name: str, host: str, port: int, scheme: str, service_type: str, confidence: int) -> DiscoveredPrinter:
    return DiscoveredPrinter(
        name=f"{name} at {host}:{port}",
        host=host,
        port=port,
        protocol=scheme,
        service_type=service_type,
        confidence=confidence,
        evidence=(f"Read-only HTTP probe matched {service_type}",),
    )


def _sort_discovered_printers(printers) -> tuple[DiscoveredPrinter, ...]:
    return tuple(sorted(printers, key=lambda printer: (-printer.confidence, printer.host, printer.port, printer.service_type)))


def _mdns_printer_metadata(service_type: str, name: str) -> tuple[str, str, int] | None:
    service_type_lower = service_type.lower()
    brand_match = _match_mdns_brand_marker(name, service_type)
    if "octoprint" in service_type_lower:
        return ("http", service_type, 90)
    if any(marker in service_type_lower for marker in ("moonraker", "klipper", "mainsail", "fluidd")):
        return ("http", service_type, 90)
    if "prusalink" in service_type_lower:
        return ("http", service_type, 88)
    if brand_match is not None:
        _, service_label, confidence = brand_match
        return ("http", service_label, confidence)
    if "_ipp._tcp" in service_type_lower or "_http._tcp" in service_type_lower:
        return None
    return None


def _prioritized_probe_ports(ports: tuple[int, ...]) -> tuple[int, ...]:
    valid_ports = tuple(dict.fromkeys(port for port in ports if 1 <= port <= 65535))[:MAX_HTTP_PROBE_PORTS]
    preferred = [port for port in PREFERRED_HTTP_PROBE_PORTS if port in valid_ports]
    remaining = [port for port in valid_ports if port not in preferred]
    return tuple(preferred + remaining)


def _match_mdns_brand_marker(name: str, service_type: str) -> tuple[str, str, int] | None:
    haystack = f"{name} {service_type}".lower()
    for marker, result in MDNS_BRAND_MARKERS.items():
        if marker in haystack:
            return result
    return None


def _resolve_probe_network(target_cidr: str | None) -> IPv4Network:
    if target_cidr:
        network = ip_network(target_cidr, strict=False)
        if network.version != 4:
            raise ValueError("Only IPv4 printer probe networks are supported")
        return network
    local_ip = _local_ipv4_address()
    return ip_network(f"{local_ip}/24", strict=False)


@lru_cache(maxsize=1)
def _local_ipv4_address() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    finally:
        probe.close()


def _limited_hosts(network: IPv4Network, max_hosts: int) -> tuple[str, ...]:
    max_hosts = max(1, min(max_hosts, 512))
    return tuple(str(host) for index, host in enumerate(network.hosts()) if index < max_hosts)
