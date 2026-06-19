from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.domains.printers.entities import PrinterScanResult
from backend.domains.printers.schemas.request import CreatePrinterRequest, PrinterScanRequest
from backend.domains.printers.schemas.response import (
    DiscoveredPrinterResponse,
    PrinterEndpointGroupResponse,
    PrinterResponse,
    PrinterScanResponse,
    PrinterScanSummaryResponse,
)
from backend.domains.printers.service import scan_lan_for_printers
from backend.domains.printers.store import PrinterStore
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/printers", tags=["printers"])


def get_printer_store(session: Session = Depends(get_db_session)) -> PrinterStore:
    return PrinterStore(session)


@router.get("", response_model=list[PrinterResponse])
def list_printers(
    _user=Depends(require_roles("viewer")),
    store: PrinterStore = Depends(get_printer_store),
) -> list[PrinterResponse]:
    return [_printer_response(printer) for printer in store.list_printers()]


@router.post("", response_model=PrinterResponse)
def create_printer(
    request: CreatePrinterRequest,
    _user=Depends(require_roles("user")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterResponse:
    printer = store.create_printer(
        name=request.name,
        host=request.host,
        port=request.port,
        protocol=request.protocol,
        printer_type=request.printer_type,
        build_volume_x_mm=request.build_volume_x_mm,
        build_volume_y_mm=request.build_volume_y_mm,
        build_volume_z_mm=request.build_volume_z_mm,
    )
    return _printer_response(printer)


@router.delete("/{printer_id}", status_code=204)
def delete_printer(
    printer_id: int,
    _user=Depends(require_roles("admin")),
    store: PrinterStore = Depends(get_printer_store),
) -> Response:
    if not store.delete_printer(printer_id):
        raise HTTPException(status_code=404, detail="Printer not found")
    return Response(status_code=204)


@router.post("/scan", response_model=PrinterScanResponse)
def scan_printers(
    request: PrinterScanRequest,
    _user=Depends(require_roles("user")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterScanResponse:
    try:
        result = scan_lan_for_printers(
            timeout_seconds=request.timeout_seconds,
            scan_method=request.scan_method,
            target_cidr=request.target_cidr,
            max_hosts=request.max_hosts,
            ports=tuple(request.ports),
            connect_timeout_seconds=request.connect_timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run = store.save_scan_result(result)
    return _scan_response(result, scan_run_id=run.id)


def _printer_response(printer) -> PrinterResponse:
    return PrinterResponse(
        id=printer.id,
        name=printer.name,
        host=printer.host,
        port=printer.port,
        protocol=printer.protocol,
        printer_type=printer.printer_type,
        state=printer.state,
        build_volume_x_mm=getattr(printer, "build_volume_x_mm", None),
        build_volume_y_mm=getattr(printer, "build_volume_y_mm", None),
        build_volume_z_mm=getattr(printer, "build_volume_z_mm", None),
    )


def _scan_response(result: PrinterScanResult, scan_run_id: int | None = None) -> PrinterScanResponse:
    printers = [_discovered_printer_response(printer) for printer in result.printers]
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
        groups=_group_discovered_printers(result.printers),
    )


def _discovered_printer_response(printer) -> DiscoveredPrinterResponse:
    return DiscoveredPrinterResponse(
        name=printer.name,
        host=printer.host,
        port=printer.port,
        protocol=printer.protocol,
        service_type=printer.service_type,
        confidence=printer.confidence,
        state=printer.state,
    )


def _group_discovered_printers(printers) -> list[PrinterEndpointGroupResponse]:
    grouped: dict[str, list] = {}
    for printer in printers:
        grouped.setdefault(printer.host, []).append(printer)

    groups = []
    for host, endpoints in grouped.items():
        ordered = sorted(endpoints, key=lambda endpoint: (-endpoint.confidence, endpoint.port, endpoint.service_type))
        capabilities = _group_capabilities(ordered)
        groups.append(
            PrinterEndpointGroupResponse(
                host=host,
                name=_group_name(host, ordered),
                inferred_type=_group_inferred_type(ordered),
                confidence=max(endpoint.confidence for endpoint in ordered),
                ports=sorted({endpoint.port for endpoint in ordered}),
                capabilities=capabilities,
                endpoints=[_discovered_printer_response(endpoint) for endpoint in ordered],
            )
        )
    return sorted(groups, key=lambda group: (-group.confidence, group.host))


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
        return ("Creality Klipper endpoint", "Fluidd/Moonraker candidate", "Optional camera endpoint candidate")
    if "moonraker" in service_type or "klipper" in service_type:
        return ("Klipper/Moonraker API", "Live status WebSocket", "Build volume and temperature metadata")
    if "bambu_mqtt" in service_type:
        return ("Bambu LAN MQTT", "Status telemetry candidate", "Requires local access code for full use")
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
