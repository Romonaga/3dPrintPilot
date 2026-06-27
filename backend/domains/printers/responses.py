from __future__ import annotations

from backend.domains.printers.entities import PrinterScanResult
from backend.domains.printers.identity import is_stable_printer_identity, printer_identity_key
from backend.domains.printers.schemas.response import (
    DiscoveredPrinterResponse,
    PrinterActionResponse,
    PrinterEndpointGroupResponse,
    PrinterResponse,
    PrinterScanResponse,
    PrinterScanSummaryResponse,
    PrinterTemperatureResponse,
)


def _action_response(printer_id: int, result) -> PrinterActionResponse:
    return PrinterActionResponse(
        printer_id=printer_id,
        action=result.action,
        accepted=result.accepted,
        raw_response=result.raw_response,
    )

def _temperature_response(temperature) -> PrinterTemperatureResponse | None:
    if temperature is None:
        return None
    return PrinterTemperatureResponse(
        current_c=temperature.current_c,
        target_c=temperature.target_c,
        power=temperature.power,
    )


def _printer_response(printer) -> PrinterResponse:
    return PrinterResponse(
        id=printer.id,
        name=printer.name,
        host=printer.host,
        port=printer.port,
        protocol=printer.protocol,
        printer_type=printer.printer_type,
        state=printer.state,
        identity_key=getattr(printer, "identity_key", None),
        adapter_type=getattr(printer, "adapter_type", None),
        capabilities=getattr(printer, "capabilities", {}) or {},
        credential_configured=getattr(printer, "credential_secret_name", None) is not None,
        last_status=getattr(printer, "last_status", {}) or {},
        last_status_at=(
            printer.last_status_at.isoformat()
            if getattr(printer, "last_status_at", None) is not None
            else None
        ),
        build_volume_x_mm=getattr(printer, "build_volume_x_mm", None),
        build_volume_y_mm=getattr(printer, "build_volume_y_mm", None),
        build_volume_z_mm=getattr(printer, "build_volume_z_mm", None),
    )


def _scan_response(
    result: PrinterScanResult,
    scan_run_id: int | None = None,
    persisted_results=None,
) -> PrinterScanResponse:
    scan_result_metadata = {
        (item.host, item.port, item.service_type): {
            "scan_result_id": item.id,
            "identity_key": getattr(item, "identity_key", None),
            "matched_printer_id": getattr(item, "matched_printer_id", None),
            "capabilities": getattr(item, "capabilities", {}) or {},
            "build_volume_x_mm": getattr(item, "build_volume_x_mm", None),
            "build_volume_y_mm": getattr(item, "build_volume_y_mm", None),
            "build_volume_z_mm": getattr(item, "build_volume_z_mm", None),
        }
        for item in (persisted_results or [])
    }
    printers = [
        _discovered_printer_response(
            printer,
            **scan_result_metadata.get((printer.host, printer.port, printer.service_type), {}),
        )
        for printer in result.printers
    ]
    return PrinterScanResponse(
        summary=PrinterScanSummaryResponse(
            scan_run_id=scan_run_id,
            status=result.summary.status.value,
            duration_ms=result.summary.duration_ms,
            discovered_count=result.summary.discovered_count,
            method=result.summary.method,
            scanned_host_count=result.summary.scanned_host_count,
            probe_count=result.summary.probe_count,
        ),
        printers=printers,
        groups=_group_discovered_printers(result.printers, scan_result_metadata),
    )


def _discovered_printer_response(
    printer,
    scan_result_id: int | None = None,
    identity_key: str | None = None,
    matched_printer_id: int | None = None,
    capabilities: dict | None = None,
    build_volume_x_mm: int | None = None,
    build_volume_y_mm: int | None = None,
    build_volume_z_mm: int | None = None,
) -> DiscoveredPrinterResponse:
    evidence = list(getattr(printer, "evidence", ()))
    resolved_identity_key = getattr(printer, "identity_key", None) or identity_key or printer_identity_key(
        name=printer.name,
        host=printer.host,
        port=printer.port,
        protocol=printer.protocol,
        service_type=printer.service_type,
        evidence=evidence,
    )
    return DiscoveredPrinterResponse(
        name=printer.name,
        host=printer.host,
        port=printer.port,
        protocol=printer.protocol,
        service_type=printer.service_type,
        confidence=printer.confidence,
        state=printer.state,
        evidence=evidence,
        scan_result_id=getattr(printer, "scan_result_id", None) or scan_result_id,
        identity_key=resolved_identity_key,
        matched_printer_id=getattr(printer, "matched_printer_id", None) or matched_printer_id,
        capabilities=getattr(printer, "capabilities", None) or capabilities or {},
        build_volume_x_mm=getattr(printer, "build_volume_x_mm", None) or build_volume_x_mm,
        build_volume_y_mm=getattr(printer, "build_volume_y_mm", None) or build_volume_y_mm,
        build_volume_z_mm=getattr(printer, "build_volume_z_mm", None) or build_volume_z_mm,
    )


def _group_discovered_printers(printers, scan_result_metadata=None) -> list[PrinterEndpointGroupResponse]:
    scan_result_metadata = scan_result_metadata or {}
    grouped: dict[str, list] = {}
    for printer in printers:
        grouped.setdefault(printer.host, []).append(printer)

    groups = []
    for host, endpoints in grouped.items():
        ordered = sorted(
            endpoints,
            key=lambda endpoint: (-endpoint.confidence, endpoint.port, endpoint.service_type),
        )
        capabilities = _group_capabilities(ordered)
        endpoint_responses = [
            _discovered_printer_response(
                endpoint,
                **scan_result_metadata.get((endpoint.host, endpoint.port, endpoint.service_type), {}),
            )
            for endpoint in ordered
        ]
        groups.append(
            PrinterEndpointGroupResponse(
                host=host,
                name=_group_name(host, ordered),
                inferred_type=_group_inferred_type(ordered),
                identity_key=_group_identity_key(endpoint_responses),
                matched_printer_id=_group_matched_printer_id(endpoint_responses),
                confidence=max(endpoint.confidence for endpoint in ordered),
                ports=sorted({endpoint.port for endpoint in ordered}),
                capabilities=capabilities,
                endpoints=endpoint_responses,
            )
        )
    return sorted(groups, key=lambda group: (-group.confidence, group.host))


def _group_identity_key(endpoints: list[DiscoveredPrinterResponse]) -> str | None:
    stable = next(
        (
            endpoint.identity_key
            for endpoint in endpoints
            if is_stable_printer_identity(endpoint.identity_key)
        ),
        None,
    )
    if stable is not None:
        return stable
    return endpoints[0].identity_key if endpoints else None


def _group_matched_printer_id(endpoints: list[DiscoveredPrinterResponse]) -> int | None:
    return next(
        (endpoint.matched_printer_id for endpoint in endpoints if endpoint.matched_printer_id is not None),
        None,
    )


def _group_name(host: str, endpoints) -> str:
    best = max(endpoints, key=lambda endpoint: endpoint.confidence)
    suffix = f" at {host}:{best.port}"
    if best.name.endswith(suffix):
        return best.name[: -len(suffix)]
    return best.name


def _group_inferred_type(endpoints) -> str:
    haystack = " ".join(endpoint.service_type.lower() + " " + endpoint.name.lower() for endpoint in endpoints)
    if "snapmaker" in haystack:
        return "Snapmaker / Moonraker"
    if "creality" in haystack or "k2plus" in haystack:
        return "Creality / Moonraker"
    if "bambu" in haystack:
        return "Bambu Lab"
    if "moonraker" in haystack or "klipper" in haystack:
        return "Klipper / Moonraker"
    if "octoprint" in haystack:
        return "OctoPrint"
    if "prusalink" in haystack:
        return "PrusaLink"
    if "duet" in haystack:
        return "Duet Web Control"
    if "ipp" in haystack:
        return "2D network printer"
    return "Possible printer service"


def _group_capabilities(endpoints) -> list[str]:
    capabilities: list[str] = []
    for endpoint in endpoints:
        for capability in _endpoint_capabilities(endpoint):
            if capability not in capabilities:
                capabilities.append(capability)
    return capabilities


def _endpoint_capabilities(endpoint) -> tuple[str, ...]:
    service_type = endpoint.service_type.lower()
    if "snapmaker" in service_type:
        return ("Snapmaker LAN API", "Klipper-compatible status", "Touchscreen-paired control candidate")
    if "creality" in service_type:
        return (
            "Creality Klipper endpoint",
            "Fluidd/Moonraker candidate",
            "Optional camera endpoint candidate",
        )
    if "moonraker" in service_type or "klipper" in service_type:
        return ("Klipper/Moonraker API", "Live status WebSocket", "Build volume and temperature metadata")
    if "bambu_mqtt" in service_type:
        return (
            "Bambu LAN MQTT",
            "Scan-only discovery without access code",
            "Full telemetry requires LAN access code",
            "LAN/Developer mode may limit Bambu Handy or cloud workflows",
        )
    if "bambu_camera" in service_type:
        return ("Bambu camera/control TCP port",)
    if "octoprint" in service_type:
        return ("OctoPrint API", "Print status and job metadata")
    if "prusalink" in service_type:
        return ("PrusaLink API", "Printer status metadata")
    if "duet" in service_type:
        return ("Duet Web Control API", "Printer status metadata")
    if "ipp" in service_type:
        return ("IPP paper printer service", "Likely not a 3D printer")
    if "possible_printer" in service_type:
        return ("Generic HTTP service candidate",)
    return (endpoint.service_type,)
