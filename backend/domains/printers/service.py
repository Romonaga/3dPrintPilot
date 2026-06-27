from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import replace
from functools import lru_cache
from ipaddress import IPv4Network, ip_network
import socket
from time import monotonic, sleep
from typing import Any
from urllib.parse import urljoin

import httpx
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from backend.domains.printers.bambu_mqtt_discovery import (
    probe_bambu_mqtt_port,
    probe_mqtt_over_tls,
)
from backend.domains.printers.identity import moonraker_identity_key
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
    "bambu a1": ("Bambu Lab A1", "mdns:bambu", 88),
    "a1 mini": ("Bambu Lab A1 mini", "mdns:bambu", 88),
    "bambu h2": ("Bambu Lab H2", "mdns:bambu", 88),
    "bambu h2d": ("Bambu Lab H2D", "mdns:bambu", 88),
    "bambu": ("Bambu Lab", "mdns:bambu", 86),
    "bblp": ("Bambu Lab", "mdns:bambu", 86),
    "k2 pro": ("Creality K2 Pro", "mdns:creality", 84),
    "k2pro": ("Creality K2 Pro", "mdns:creality", 84),
    "creality k2": ("Creality K2", "mdns:creality", 82),
    "creality": ("Creality", "mdns:creality", 80),
    "snapmaker u1": ("Snapmaker U1", "mdns:snapmaker", 82),
    "snapmaker": ("Snapmaker", "mdns:snapmaker", 80),
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
    timeout_seconds: float = 20.0,
    scan_method: str = "combined",
    target_cidr: str | None = None,
    max_hosts: int = 254,
    ports: tuple[int, ...] | None = None,
    connect_timeout_seconds: float = 2.0,
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


def merge_known_printer_discoveries(
    result: PrinterScanResult,
    known_printers,
    timeout_seconds: float = 1.0,
) -> PrinterScanResult:
    printers = list(result.printers)
    probe_count = 0
    for known_printer in known_printers:
        if _known_printer_already_discovered(known_printer, printers):
            continue
        probe_count += 1
        discovered = probe_known_printer_endpoint(known_printer, timeout_seconds=timeout_seconds)
        if discovered is not None:
            printers.append(discovered)
    if probe_count == 0:
        return result
    sorted_printers = _sort_discovered_printers(printers)
    return replace(
        result,
        summary=replace(
            result.summary,
            discovered_count=len(sorted_printers),
            probe_count=result.summary.probe_count + probe_count,
        ),
        printers=sorted_printers,
    )


def probe_known_printer_endpoint(known_printer, timeout_seconds: float = 1.0) -> DiscoveredPrinter | None:
    host = getattr(known_printer, "host", None)
    port = getattr(known_printer, "port", None)
    protocol = (getattr(known_printer, "protocol", None) or "http").lower()
    if not host or not port:
        return None

    first_reachable_endpoint = None
    for endpoint_protocol, endpoint_port, endpoint_timeout in _known_printer_probe_endpoints(
        protocol,
        int(port),
        timeout_seconds,
    ):
        detected = _probe_known_endpoint(host, endpoint_port, endpoint_protocol, endpoint_timeout)
        if detected is not None:
            return _merge_known_printer_metadata(detected, known_printer)
        if first_reachable_endpoint is None and _tcp_port_open(host, endpoint_port, endpoint_timeout):
            first_reachable_endpoint = (endpoint_protocol, endpoint_port)

    if first_reachable_endpoint is None:
        return None
    fallback_protocol, fallback_port = first_reachable_endpoint

    return DiscoveredPrinter(
        name=getattr(known_printer, "name", None) or f"Known printer at {host}:{fallback_port}",
        host=host,
        port=fallback_port,
        protocol=fallback_protocol,
        service_type=_known_printer_service_type(known_printer),
        confidence=76,
        state="known",
        evidence=(f"Configured printer host is reachable at {fallback_protocol}://{host}:{fallback_port}",),
        identity_key=getattr(known_printer, "identity_key", None),
        matched_printer_id=getattr(known_printer, "id", None),
        capabilities=getattr(known_printer, "capabilities", None) or {},
        build_volume_x_mm=getattr(known_printer, "build_volume_x_mm", None),
        build_volume_y_mm=getattr(known_printer, "build_volume_y_mm", None),
        build_volume_z_mm=getattr(known_printer, "build_volume_z_mm", None),
    )


def _known_printer_probe_endpoints(
    protocol: str,
    port: int,
    timeout_seconds: float,
) -> tuple[tuple[str, int, float], ...]:
    fallback_timeout = min(timeout_seconds, 0.5)
    endpoints = [(protocol, port, timeout_seconds)]
    for candidate_port in PREFERRED_HTTP_PROBE_PORTS:
        candidate_protocol = "mqtts" if candidate_port == 8883 else "https" if candidate_port == 443 else "http"
        candidate = (candidate_protocol, candidate_port, fallback_timeout)
        if candidate_port != port and candidate not in endpoints:
            endpoints.append(candidate)
    return tuple(endpoints)


def _probe_known_endpoint(
    host: str,
    port: int,
    protocol: str,
    timeout_seconds: float,
) -> DiscoveredPrinter | None:
    if protocol in {"http", "https"}:
        return _probe_http_port(host, port, timeout_seconds)
    if protocol == "mqtts" or port == 8883:
        return _probe_bambu_mqtt_port(host, port, timeout_seconds)
    return None


def _known_printer_already_discovered(known_printer, discovered_printers: list[DiscoveredPrinter]) -> bool:
    known_identity = getattr(known_printer, "identity_key", None)
    known_host = getattr(known_printer, "host", None)
    known_port = getattr(known_printer, "port", None)
    known_protocol = getattr(known_printer, "protocol", None)
    for discovered in discovered_printers:
        if known_identity and discovered.identity_key and known_identity == discovered.identity_key:
            return True
        if (
            known_host == discovered.host
            and known_port == discovered.port
            and known_protocol == discovered.protocol
        ):
            return True
    return False


def _merge_known_printer_metadata(discovered: DiscoveredPrinter, known_printer) -> DiscoveredPrinter:
    known_capabilities = getattr(known_printer, "capabilities", None) or {}
    discovered_capabilities = discovered.capabilities or {}
    return replace(
        discovered,
        identity_key=discovered.identity_key or getattr(known_printer, "identity_key", None),
        matched_printer_id=getattr(known_printer, "id", None),
        capabilities={**known_capabilities, **discovered_capabilities},
        build_volume_x_mm=discovered.build_volume_x_mm or getattr(known_printer, "build_volume_x_mm", None),
        build_volume_y_mm=discovered.build_volume_y_mm or getattr(known_printer, "build_volume_y_mm", None),
        build_volume_z_mm=discovered.build_volume_z_mm or getattr(known_printer, "build_volume_z_mm", None),
        evidence=tuple(
            list(discovered.evidence)
            + [f"Matched configured printer endpoint {known_printer.host}:{known_printer.port}"]
        ),
    )


def _known_printer_service_type(known_printer) -> str:
    printer_type = (getattr(known_printer, "printer_type", None) or "").strip()
    if printer_type:
        return printer_type
    adapter_type = (getattr(known_printer, "adapter_type", None) or "").strip()
    if adapter_type:
        return f"known:{adapter_type}"
    return "known:printer"


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
    candidate_hosts = _hosts_with_open_probe_ports(hosts, checked_ports, connect_timeout_seconds)

    executor = ThreadPoolExecutor(max_workers=min(32, max(1, len(candidate_hosts))))
    futures = [
        executor.submit(_probe_host_ports, host, checked_ports, connect_timeout_seconds)
        for host in candidate_hosts
    ]
    try:
        completed_futures = as_completed(
            futures,
            timeout=max(scan_timeout_seconds, 0.1) if scan_timeout_seconds is not None else None,
        )
        for future in completed_futures:
            try:
                printers = future.result()
            except Exception:
                continue
            for printer in printers:
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


def _hosts_with_open_probe_ports(
    hosts: tuple[str, ...],
    ports: tuple[int, ...],
    timeout_seconds: float,
) -> tuple[str, ...]:
    open_hosts: set[str] = set()
    if not hosts or not ports:
        return ()

    executor = ThreadPoolExecutor(max_workers=min(128, max(1, len(hosts))))
    futures = {executor.submit(_host_has_open_probe_port, host, ports, timeout_seconds): host for host in hosts}
    try:
        for future in as_completed(futures):
            host = futures[future]
            try:
                if future.result():
                    open_hosts.add(host)
            except Exception:
                continue
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return tuple(host for host in hosts if host in open_hosts)


def _host_has_open_probe_port(host: str, ports: tuple[int, ...], timeout_seconds: float) -> bool:
    return any(_tcp_port_open(host, port, timeout_seconds) for port in ports)


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
    best_printer: DiscoveredPrinter | None = None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, verify=True) as client:
            for path, detector in _probe_paths(port):
                try:
                    response = client.get(urljoin(base_url, path))
                except httpx.HTTPError:
                    continue
                printer = detector(host, port, scheme, response)
                if printer is not None:
                    if "moonraker" in printer.service_type:
                        printer = _enrich_moonraker_discovery(client, base_url, printer)
                    if best_printer is None or printer.confidence > best_printer.confidence:
                        best_printer = printer
                    if printer.confidence >= 94:
                        return printer
    except httpx.HTTPError:
        return best_printer
    return best_printer


def _enrich_moonraker_discovery(
    client: httpx.Client,
    base_url: str,
    printer: DiscoveredPrinter,
) -> DiscoveredPrinter:
    try:
        response = client.get(
            f"{base_url}/printer/objects/query?configfile&toolhead&extruder&heater_bed"
        )
    except httpx.HTTPError:
        return printer
    if response.status_code != 200:
        return printer
    payload = _response_json(response)
    if not payload:
        return printer
    capabilities = _moonraker_capabilities_from_objects(payload, printer.service_type)
    if not capabilities:
        return printer
    build_volume = capabilities.pop("build_volume_mm", {})
    evidence = tuple(
        list(printer.evidence)
        + ["Read-only Moonraker object query exposed deterministic capability metadata"]
    )
    return replace(
        printer,
        capabilities={**(printer.capabilities or {}), **capabilities},
        build_volume_x_mm=_int_or_none(build_volume.get("x")),
        build_volume_y_mm=_int_or_none(build_volume.get("y")),
        build_volume_z_mm=_int_or_none(build_volume.get("z")),
        evidence=evidence,
    )


def _moonraker_capabilities_from_objects(payload: dict[str, Any], service_type: str) -> dict[str, Any]:
    result = payload.get("result", payload)
    status = result.get("status", result) if isinstance(result, dict) else {}
    if not isinstance(status, dict):
        return {}
    configfile = status.get("configfile", {})
    settings = {}
    if isinstance(configfile, dict):
        settings = configfile.get("settings") or configfile.get("config") or {}
    if not isinstance(settings, dict):
        settings = {}

    capabilities: dict[str, Any] = {}
    has_fact = False
    volume = _moonraker_build_volume(status, settings)
    if volume:
        capabilities["build_volume_mm"] = volume
        has_fact = True

    extruder_names = _moonraker_extruder_names(status, settings)
    if extruder_names:
        capabilities["extruder_count"] = len(extruder_names)
        capabilities["toolhead_count"] = len(extruder_names)
        has_fact = True
        if len(extruder_names) > 1:
            capabilities["multi_head"] = True
            capabilities["color_count"] = len(extruder_names)
            capabilities["multi_color"] = True
    max_nozzle_temp = _max_config_number(settings, extruder_names, "max_temp")
    if max_nozzle_temp is not None:
        capabilities["max_nozzle_temp_c"] = max_nozzle_temp
        has_fact = True
    nozzle_diameter = _max_config_number(settings, extruder_names, "nozzle_diameter")
    if nozzle_diameter is not None:
        capabilities["nozzle_diameter_mm"] = nozzle_diameter
        has_fact = True
    bed = settings.get("heater_bed") if isinstance(settings.get("heater_bed"), dict) else {}
    max_bed_temp = _float_or_none(bed.get("max_temp") if isinstance(bed, dict) else None)
    if max_bed_temp is not None:
        capabilities["max_bed_temp_c"] = max_bed_temp
        has_fact = True

    if not has_fact:
        return {}

    if "snapmaker" in service_type.lower() and capabilities.get("toolhead_count"):
        capabilities["known_multi_head_candidate"] = True
    return {
        "adapter": "moonraker",
        "read_only_status": True,
        "capability_source": "moonraker_object_query",
        **capabilities,
    }


def _moonraker_build_volume(status: dict[str, Any], settings: dict[str, Any]) -> dict[str, int] | None:
    toolhead = status.get("toolhead") if isinstance(status.get("toolhead"), dict) else {}
    axis_maximum = toolhead.get("axis_maximum") if isinstance(toolhead, dict) else None
    if isinstance(axis_maximum, (list, tuple)) and len(axis_maximum) >= 3:
        volume = {
            "x": _int_or_none(axis_maximum[0]),
            "y": _int_or_none(axis_maximum[1]),
            "z": _int_or_none(axis_maximum[2]),
        }
        if all(value is not None and value > 0 for value in volume.values()):
            return volume
    x = _axis_span(settings, "stepper_x")
    y = _axis_span(settings, "stepper_y")
    z = _axis_span(settings, "stepper_z")
    if x and y and z:
        return {"x": x, "y": y, "z": z}
    return None


def _axis_span(settings: dict[str, Any], axis_key: str) -> int | None:
    axis = settings.get(axis_key)
    if not isinstance(axis, dict):
        return None
    position_max = _float_or_none(axis.get("position_max"))
    position_min = _float_or_none(axis.get("position_min")) or 0
    if position_max is None:
        return None
    span = round(position_max - position_min)
    return span if span > 0 else None


def _moonraker_extruder_names(status: dict[str, Any], settings: dict[str, Any]) -> tuple[str, ...]:
    names = set()
    for source in (status, settings):
        for key in source:
            if key == "extruder" or (key.startswith("extruder") and key[8:].isdigit()):
                names.add(key)
    return tuple(sorted(names, key=lambda name: (len(name), name)))


def _max_config_number(settings: dict[str, Any], section_names: tuple[str, ...], key: str) -> float | None:
    values = []
    for section_name in section_names:
        section = settings.get(section_name)
        if isinstance(section, dict):
            value = _float_or_none(section.get(key))
            if value is not None:
                values.append(value)
    return max(values) if values else None


def _float_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _probe_bambu_mqtt_port(host: str, port: int, timeout_seconds: float) -> DiscoveredPrinter | None:
    return probe_bambu_mqtt_port(host, port, timeout_seconds, mqtt_probe=_probe_mqtt_over_tls)


def _probe_mqtt_over_tls(host: str, port: int, timeout_seconds: float) -> str:
    return probe_mqtt_over_tls(host, port, timeout_seconds)


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
    payload = _response_json(response)
    if response.status_code == 200 and "snapmakercloud" in text:
        return _http_printer(
            "Snapmaker U1 Moonraker",
            host,
            port,
            scheme,
            "http_probe:snapmaker_moonraker",
            94,
            identity_key=moonraker_identity_key(payload, "snapmaker_moonraker"),
        )
    if response.status_code == 200 and any(marker in text for marker in ("k2 pro", "k2pro")):
        return _http_printer(
            "Creality K2 Pro Moonraker",
            host,
            port,
            scheme,
            "http_probe:creality_moonraker",
            94,
            identity_key=moonraker_identity_key(payload, "creality_moonraker"),
        )
    if response.status_code == 200 and any(marker in text for marker in ("k2 plus", "k2plus")):
        return _http_printer(
            "Creality K2 Plus Moonraker",
            host,
            port,
            scheme,
            "http_probe:creality_moonraker",
            94,
            identity_key=moonraker_identity_key(payload, "creality_moonraker"),
        )
    if response.status_code == 200 and ("moonraker" in text or "klippy" in text or "klipper" in text):
        return _http_printer(
            "Moonraker",
            host,
            port,
            scheme,
            "http_probe:moonraker",
            92,
            identity_key=moonraker_identity_key(payload, "moonraker"),
        )
    return None


def _detect_duet(host: str, port: int, scheme: str, response: httpx.Response) -> DiscoveredPrinter | None:
    text = response.text.lower()
    if response.status_code == 200 and ("status" in text or "coords" in text) and ("seq" in text or "temps" in text):
        return _http_printer("Duet Web Control", host, port, scheme, "http_probe:duet", 82)
    return None


def _detect_generic_http(host: str, port: int, scheme: str, response: httpx.Response) -> DiscoveredPrinter | None:
    text = response.text.lower()
    server = response.headers.get("server", "").lower()
    haystack = f"{server}\n{text}"
    contextual_match = _match_http_contextual_marker(haystack)
    if contextual_match is not None:
        name, service_type, confidence = contextual_match
        return _http_printer(name, host, port, scheme, service_type, confidence)
    markers = {
        "octoprint": ("OctoPrint", "http_probe:octoprint", 88),
        "creality k2 pro": ("Creality K2 Pro", "http_probe:creality", 88),
        "k2 pro": ("Creality K2 Pro", "http_probe:creality", 88),
        "k2pro": ("Creality K2 Pro", "http_probe:creality", 88),
        "creality k2 plus": ("Creality K2 Plus", "http_probe:creality", 86),
        "k2 plus": ("Creality K2 Plus", "http_probe:creality", 86),
        "k2plus": ("Creality K2 Plus", "http_probe:creality", 86),
        "creality": ("Creality", "http_probe:creality", 84),
        "creality k2": ("Creality K2", "http_probe:creality", 84),
        "bambu h2d": ("Bambu Lab H2D", "http_probe:bambu", 82),
        "bambu h2": ("Bambu Lab H2", "http_probe:bambu", 82),
        "bambu a1": ("Bambu Lab A1", "http_probe:bambu", 82),
        "moonraker": ("Moonraker", "http_probe:moonraker", 88),
        "klipper": ("Klipper/Moonraker", "http_probe:moonraker", 84),
        "mainsail": ("Mainsail/Klipper", "http_probe:moonraker", 82),
        "fluidd": ("Fluidd/Klipper", "http_probe:moonraker", 82),
        "prusalink": ("PrusaLink", "http_probe:prusalink", 84),
        "prusa link": ("PrusaLink", "http_probe:prusalink", 84),
        "duet": ("Duet Web Control", "http_probe:duet", 78),
        "bambu": ("Bambu Lab", "http_probe:bambu", 78),
        "snapmaker u1": ("Snapmaker U1", "http_probe:snapmaker", 82),
        "snapmaker": ("Snapmaker", "http_probe:snapmaker", 78),
    }
    for marker, (name, service_type, confidence) in markers.items():
        if marker in haystack:
            return _http_printer(name, host, port, scheme, service_type, confidence)
    return None


def _http_printer(
    name: str,
    host: str,
    port: int,
    scheme: str,
    service_type: str,
    confidence: int,
    identity_key: str | None = None,
) -> DiscoveredPrinter:
    return DiscoveredPrinter(
        name=f"{name} at {host}:{port}",
        host=host,
        port=port,
        protocol=scheme,
        service_type=service_type,
        confidence=confidence,
        evidence=(f"Read-only HTTP probe matched {service_type}",),
        identity_key=identity_key,
    )


def _response_json(response: httpx.Response) -> dict | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


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


def _match_http_contextual_marker(haystack: str) -> tuple[str, str, int] | None:
    if "bambu" in haystack:
        if "h2d" in haystack:
            return ("Bambu Lab H2D", "http_probe:bambu", 82)
        if "h2" in haystack:
            return ("Bambu Lab H2", "http_probe:bambu", 82)
        if "a1 mini" in haystack:
            return ("Bambu Lab A1 mini", "http_probe:bambu", 82)
        if "a1" in haystack:
            return ("Bambu Lab A1", "http_probe:bambu", 82)
    if "snapmaker" in haystack and "u1" in haystack:
        return ("Snapmaker U1", "http_probe:snapmaker", 82)
    if "creality" in haystack:
        if "k2 pro" in haystack or "k2pro" in haystack:
            return ("Creality K2 Pro", "http_probe:creality", 88)
        if "k2 plus" in haystack or "k2plus" in haystack:
            return ("Creality K2 Plus", "http_probe:creality", 86)
    return None


def _match_mdns_brand_marker(name: str, service_type: str) -> tuple[str, str, int] | None:
    name_lower = name.lower()
    haystack = f"{name_lower} {service_type}".lower()
    if any(marker in haystack for marker in ("bambu", "bblp")):
        if "h2d" in name_lower:
            return ("Bambu Lab H2D", "mdns:bambu", 88)
        if "h2" in name_lower:
            return ("Bambu Lab H2", "mdns:bambu", 88)
        if "a1 mini" in name_lower:
            return ("Bambu Lab A1 mini", "mdns:bambu", 88)
        if "a1" in name_lower:
            return ("Bambu Lab A1", "mdns:bambu", 88)
        return ("Bambu Lab", "mdns:bambu", 86)
    if "creality" in haystack:
        if "k2 pro" in name_lower or "k2pro" in name_lower:
            return ("Creality K2 Pro", "mdns:creality", 84)
        if "k2 plus" in name_lower or "k2plus" in name_lower:
            return ("Creality K2 Plus", "mdns:creality", 84)
        if "k2" in name_lower:
            return ("Creality K2", "mdns:creality", 82)
        return ("Creality", "mdns:creality", 80)
    if "snapmaker" in haystack:
        if "u1" in name_lower:
            return ("Snapmaker U1", "mdns:snapmaker", 82)
        return ("Snapmaker", "mdns:snapmaker", 80)
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
