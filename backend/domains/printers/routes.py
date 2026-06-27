from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
import httpx
from sqlalchemy.orm import Session

from backend.core.database import get_db_session
from backend.core.secrets import get_secret_cipher
from backend.domains.printers.adapters import (
    ExtensionMethodNotAllowedError,
    InvalidPrintFileError,
    UnsupportedPrinterControlError,
    cancel_moonraker_print,
    engine_catalog,
    fetch_moonraker_capability_diagnostics,
    fetch_moonraker_job_status,
    fetch_read_only_status,
    list_moonraker_files,
    pause_moonraker_print,
    refresh_engine_catalog,
    request_moonraker_extension,
    resume_moonraker_print,
    start_moonraker_print,
    upload_moonraker_file,
)
from backend.domains.printers.credentials import (
    configure_bambu_lan_credentials,
    delete_bambu_lan_credentials,
    get_bambu_lan_access_code,
)
from backend.domains.printers.responses import (
    _action_response,
    _endpoint_capabilities,
    _printer_response,
    _scan_response,
    _temperature_response,
)
from backend.domains.printers.schemas.request import (
    BambuLanCredentialsRequest,
    ConfirmDiscoveredPrinterRequest,
    CreatePrinterRequest,
    PrinterExtensionRequest,
    PrintFileRequest,
    PrinterScanRequest,
    UpdatePrinterRequest,
)
from backend.domains.printers.schemas.response import (
    PrinterActionResponse,
    PrinterCapabilityDiagnosticsResponse,
    PrinterCredentialResponse,
    PrinterEngineResponse,
    PrinterExtensionResponse,
    PrinterFileResponse,
    PrinterJobStatusResponse,
    PrinterResponse,
    PrinterScanResponse,
    PrinterStatusResponse,
    PrinterToolheadTelemetryResponse,
)
from backend.domains.printers.service import merge_known_printer_discoveries, scan_lan_for_printers
from backend.domains.printers.store import PrinterStore
from backend.domains.users.dependencies import require_roles

router = APIRouter(prefix="/printers", tags=["printers"])

__all__ = ["_endpoint_capabilities", "get_printer_store", "router"]


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


@router.get("/engines", response_model=list[PrinterEngineResponse])
def list_printer_engines(
    _user=Depends(require_roles("viewer")),
) -> list[PrinterEngineResponse]:
    return [PrinterEngineResponse(**engine) for engine in engine_catalog()]


@router.post("/engines/refresh", response_model=list[PrinterEngineResponse])
def refresh_printer_engines(
    _user=Depends(require_roles("admin")),
) -> list[PrinterEngineResponse]:
    refresh_engine_catalog()
    return [PrinterEngineResponse(**engine) for engine in engine_catalog()]


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
    session: Session = Depends(get_db_session),
) -> PrinterStatusResponse:
    printer = _get_printer_or_404(store, printer_id)
    access_code = None
    if getattr(printer, "adapter_type", None) == "bambu_mqtt" and getattr(printer, "credential_secret_name", None):
        access_code = get_bambu_lan_access_code(session, get_secret_cipher(), printer)
    try:
        status = fetch_read_only_status(printer, api_key=access_code)
    except (httpx.HTTPError, ValueError) as exc:
        raise _printer_telemetry_exception(exc) from exc
    return PrinterStatusResponse(
        printer_id=printer.id,
        adapter_type=status.adapter_type,
        state=status.state,
        capabilities=status.capabilities,
        raw_status=status.raw_status,
        observed_at=status.observed_at.isoformat(),
    )


@router.put("/{printer_id}/credentials/bambu-lan", response_model=PrinterCredentialResponse)
def configure_printer_bambu_lan_credentials(
    printer_id: int,
    request: BambuLanCredentialsRequest,
    _user=Depends(require_roles("admin")),
    store: PrinterStore = Depends(get_printer_store),
    session: Session = Depends(get_db_session),
) -> PrinterCredentialResponse:
    printer = _get_printer_or_404(store, printer_id)
    if getattr(printer, "adapter_type", None) != "bambu_mqtt":
        raise HTTPException(status_code=409, detail="Bambu LAN credentials are only supported for Bambu MQTT printers")
    try:
        updated = configure_bambu_lan_credentials(
            session,
            get_secret_cipher(),
            printer,
            access_code=request.access_code,
            device_id=request.device_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PrinterCredentialResponse(
        printer_id=updated.id,
        credential_configured=True,
        device_id_configured=bool((updated.capabilities or {}).get("device_id")),
    )


@router.delete("/{printer_id}/credentials/bambu-lan", response_model=PrinterCredentialResponse)
def delete_printer_bambu_lan_credentials(
    printer_id: int,
    _user=Depends(require_roles("admin")),
    store: PrinterStore = Depends(get_printer_store),
    session: Session = Depends(get_db_session),
) -> PrinterCredentialResponse:
    printer = _get_printer_or_404(store, printer_id)
    delete_bambu_lan_credentials(session, printer)
    return PrinterCredentialResponse(
        printer_id=printer.id,
        credential_configured=False,
        device_id_configured=False,
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
    except (httpx.HTTPError, ValueError) as exc:
        raise _printer_telemetry_exception(exc) from exc
    return PrinterJobStatusResponse(
        printer_id=printer.id,
        state=status.state,
        filename=status.filename,
        progress=status.progress,
        message=status.message,
        bed_temperature=_temperature_response(status.bed_temperature),
        toolheads=[
            PrinterToolheadTelemetryResponse(
                name=toolhead.name,
                label=toolhead.label,
                index=toolhead.index,
                current_temperature=_temperature_response(toolhead.current_temperature),
                color=toolhead.color,
                color_source=toolhead.color_source,
                material=toolhead.material,
                material_source=toolhead.material_source,
                vendor=toolhead.vendor,
                subtype=toolhead.subtype,
            )
            for toolhead in status.toolheads
        ],
        raw_status=status.raw_status,
        observed_at=status.observed_at.isoformat(),
    )


@router.get("/{printer_id}/capability-diagnostics", response_model=PrinterCapabilityDiagnosticsResponse)
def read_printer_capability_diagnostics(
    printer_id: int,
    _user=Depends(require_roles("viewer")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterCapabilityDiagnosticsResponse:
    printer = _get_printer_or_404(store, printer_id)
    try:
        diagnostics = fetch_moonraker_capability_diagnostics(printer)
    except UnsupportedPrinterControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise _printer_telemetry_exception(exc) from exc
    return PrinterCapabilityDiagnosticsResponse(
        printer_id=printer.id,
        adapter_type=diagnostics.adapter_type,
        extension_agents_available=diagnostics.extension_agents_available,
        extension_agents=list(diagnostics.extension_agents),
        spoolman_available=diagnostics.spoolman_available,
        spoolman_status=diagnostics.spoolman_status,
        probe_errors=diagnostics.probe_errors,
        observed_at=diagnostics.observed_at.isoformat(),
    )


@router.post("/{printer_id}/extensions/request", response_model=PrinterExtensionResponse)
def request_printer_extension(
    printer_id: int,
    request: PrinterExtensionRequest,
    _user=Depends(require_roles("admin")),
    store: PrinterStore = Depends(get_printer_store),
) -> PrinterExtensionResponse:
    printer = _get_printer_or_404(store, printer_id)
    try:
        result = request_moonraker_extension(
            printer,
            agent=request.agent,
            method=request.method,
            arguments=request.arguments,
        )
    except ExtensionMethodNotAllowedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except UnsupportedPrinterControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PrinterExtensionResponse(
        printer_id=printer.id,
        agent=result.agent,
        method=result.method,
        accepted=result.accepted,
        raw_response=result.raw_response,
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
    result = merge_known_printer_discoveries(
        result,
        store.list_printers(),
        timeout_seconds=request.connect_timeout_seconds,
    )
    run = store.save_scan_result(result)
    return _scan_response(result, scan_run_id=run.id, persisted_results=run.results)


def _get_printer_or_404(store: PrinterStore, printer_id: int):
    printer = next((candidate for candidate in store.list_printers() if candidate.id == printer_id), None)
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    return printer


def _printer_telemetry_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, httpx.TimeoutException):
        return HTTPException(status_code=504, detail="Printer telemetry timed out")
    return HTTPException(status_code=502, detail="Printer telemetry is unavailable")


def _run_print_action(store: PrinterStore, printer_id: int, action) -> PrinterActionResponse:
    printer = _get_printer_or_404(store, printer_id)
    try:
        result = action(printer)
    except UnsupportedPrinterControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _action_response(printer.id, result)
