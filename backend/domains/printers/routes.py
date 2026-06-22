from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.domains.printers.adapters import (
    InvalidPrintFileError,
    UnsupportedPrinterControlError,
    cancel_moonraker_print,
    fetch_moonraker_job_status,
    fetch_read_only_status,
    list_moonraker_files,
    pause_moonraker_print,
    resume_moonraker_print,
    start_moonraker_print,
    upload_moonraker_file,
)
from backend.domains.printers.entities import PrinterScanResult
from backend.domains.printers.identity import is_stable_printer_identity, printer_identity_key
from backend.domains.printers.schemas.request import (
    ConfirmDiscoveredPrinterRequest,
    CreatePrinterRequest,
    PrintFileRequest,
    PrinterScanRequest,
    UpdatePrinterRequest,
)
from backend.domains.printers.schemas.response import (
    DiscoveredPrinterResponse,
    PrinterActionResponse,
    PrinterEndpointGroupResponse,
    PrinterFileResponse,
    PrinterJobStatusResponse,
    PrinterResponse,
    PrinterScanResponse,
    PrinterScanSummaryResponse,
    PrinterStatusResponse,
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


@router.put("/{printer_id}", response_model=PrinterResponse)
def update_printer(
    printer_id: int,
    request: UpdatePrinterRequest,
    _user=Depends(require_roles("admin")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterResponse:
    printer = store.update_printer(printer_id, **request.model_dump(exclude_unset=True))
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    return _printer_response(printer)


@router.post("/confirm-discovered", response_model=PrinterResponse)
def confirm_discovered_printer(
    request: ConfirmDiscoveredPrinterRequest,
    _user=Depends(require_roles("admin")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterResponse:
    printer = store.confirm_discovered_printer(
        name=request.name,
        host=request.host,
        port=request.port,
        protocol=request.protocol,
        service_type=request.service_type,
        identity_key=request.identity_key,
        capabilities=request.capabilities,
        scan_result_id=request.scan_result_id,
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


@router.get("/{printer_id}/status", response_model=PrinterStatusResponse)
def read_printer_status(
    printer_id: int,
    _user=Depends(require_roles("viewer")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterStatusResponse:
    printer = _get_printer_or_404(store, printer_id)
    status = fetch_read_only_status(printer)
    return PrinterStatusResponse(
        printer_id=printer.id,
        adapter_type=status.adapter_type,
        state=status.state,
        capabilities=status.capabilities,
        raw_status=status.raw_status,
        observed_at=status.observed_at.isoformat(),
    )


@router.get("/{printer_id}/job-status", response_model=PrinterJobStatusResponse)
def read_printer_job_status(
    printer_id: int,
    _user=Depends(require_roles("viewer")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterJobStatusResponse:
    printer = _get_printer_or_404(store, printer_id)
    try:
        status = fetch_moonraker_job_status(printer)
    except UnsupportedPrinterControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PrinterJobStatusResponse(
        printer_id=printer.id,
        state=status.state,
        filename=status.filename,
        progress=status.progress,
        message=status.message,
        raw_status=status.raw_status,
        observed_at=status.observed_at.isoformat(),
    )


@router.get("/{printer_id}/files", response_model=list[PrinterFileResponse])
def list_printer_files(
    printer_id: int,
    _user=Depends(require_roles("viewer")),
    store: PrinterStore = Depends(get_printer_store),
) -> list[PrinterFileResponse]:
    printer = _get_printer_or_404(store, printer_id)
    try:
        files = list_moonraker_files(printer)
    except UnsupportedPrinterControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return [
        PrinterFileResponse(path=item.path, size=item.size, modified=item.modified, permissions=item.permissions)
        for item in files
    ]


@router.post("/{printer_id}/files", response_model=PrinterActionResponse, status_code=201)
async def upload_printer_file(
    printer_id: int,
    file: UploadFile = File(...),
    _user=Depends(require_roles("user")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterActionResponse:
    printer = _get_printer_or_404(store, printer_id)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded print file is empty")
    try:
        result = upload_moonraker_file(
            printer,
            filename=file.filename or "",
            content=content,
            content_type=file.content_type,
        )
    except InvalidPrintFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnsupportedPrinterControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _action_response(printer.id, result)


@router.post("/{printer_id}/print/start", response_model=PrinterActionResponse)
def start_printer_file(
    printer_id: int,
    request: PrintFileRequest,
    _user=Depends(require_roles("user")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterActionResponse:
    printer = _get_printer_or_404(store, printer_id)
    try:
        result = start_moonraker_print(printer, request.filename)
    except InvalidPrintFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnsupportedPrinterControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _action_response(printer.id, result)


@router.post("/{printer_id}/print/pause", response_model=PrinterActionResponse)
def pause_printer_print(
    printer_id: int,
    _user=Depends(require_roles("user")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterActionResponse:
    return _run_print_action(store, printer_id, pause_moonraker_print)


@router.post("/{printer_id}/print/resume", response_model=PrinterActionResponse)
def resume_printer_print(
    printer_id: int,
    _user=Depends(require_roles("user")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterActionResponse:
    return _run_print_action(store, printer_id, resume_moonraker_print)


@router.post("/{printer_id}/print/cancel", response_model=PrinterActionResponse)
def cancel_printer_print(
    printer_id: int,
    _user=Depends(require_roles("user")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterActionResponse:
    return _run_print_action(store, printer_id, cancel_moonraker_print)


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
    return _scan_response(result, scan_run_id=run.id, persisted_results=run.results)


def _get_printer_or_404(store: PrinterStore, printer_id: int):
    printer = next((candidate for candidate in store.list_printers() if candidate.id == printer_id), None)
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    return printer


def _action_response(printer_id: int, result) -> PrinterActionResponse:
    return PrinterActionResponse(
        printer_id=printer_id,
        action=result.action,
        accepted=result.accepted,
        raw_response=result.raw_response,
    )


def _run_print_action(store: PrinterStore, printer_id: int, action) -> PrinterActionResponse:
    printer = _get_printer_or_404(store, printer_id)
    try:
        result = action(printer)
    except UnsupportedPrinterControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _action_response(printer.id, result)


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
