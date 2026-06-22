from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domains.printers.adapters import capabilities_for_service_type, infer_adapter_type
from backend.domains.printers.entities import PrinterScanResult
from backend.domains.printers.identity import is_stable_printer_identity, printer_identity_key
from backend.domains.printers.models import NetworkScanResult, NetworkScanRun, Printer


class PrinterStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_printers(self) -> list[Printer]:
        return list(self._session.scalars(select(Printer).order_by(Printer.name)))

    def create_printer(
        self,
        name: str,
        host: str,
        port: int,
        protocol: str = "http",
        printer_type: str = "unknown",
        build_volume_x_mm: int | None = None,
        build_volume_y_mm: int | None = None,
        build_volume_z_mm: int | None = None,
        state: str = "manual",
        identity_key: str | None = None,
        adapter_type: str | None = None,
        capabilities: dict | None = None,
    ) -> Printer:
        printer = Printer(
            name=name,
            host=host,
            port=port,
            protocol=protocol,
            printer_type=printer_type,
            state=state,
            identity_key=identity_key,
            adapter_type=adapter_type or infer_adapter_type(None, printer_type),
            capabilities=capabilities or capabilities_for_service_type(printer_type),
            build_volume_x_mm=build_volume_x_mm,
            build_volume_y_mm=build_volume_y_mm,
            build_volume_z_mm=build_volume_z_mm,
        )
        self._session.add(printer)
        self._session.commit()
        self._session.refresh(printer)
        return printer

    def update_printer(self, printer_id: int, **updates) -> Printer | None:
        printer = self._session.get(Printer, printer_id)
        if printer is None:
            return None
        for field_name, value in updates.items():
            if value is not None and hasattr(printer, field_name):
                setattr(printer, field_name, value)
        if updates.get("printer_type") is not None:
            printer.adapter_type = infer_adapter_type(None, printer.printer_type)
            printer.capabilities = capabilities_for_service_type(printer.printer_type)
        self._session.commit()
        self._session.refresh(printer)
        return printer

    def confirm_discovered_printer(
        self,
        name: str,
        host: str,
        port: int,
        protocol: str,
        service_type: str,
        identity_key: str | None = None,
        build_volume_x_mm: int | None = None,
        build_volume_y_mm: int | None = None,
        build_volume_z_mm: int | None = None,
        capabilities: dict | None = None,
        scan_result_id: int | None = None,
    ) -> Printer:
        source = self._session.get(NetworkScanResult, scan_result_id) if scan_result_id is not None else None
        final_service_type = source.service_type if source is not None else service_type
        final_name = source.name if source is not None else name
        final_host = source.host if source is not None else host
        final_port = source.port if source is not None else port
        final_protocol = source.protocol if source is not None else protocol
        final_capabilities = _merge_capabilities(
            capabilities_for_service_type(final_service_type),
            getattr(source, "capabilities", None) if source is not None else None,
            capabilities,
        )
        final_build_volume_x_mm = build_volume_x_mm or (getattr(source, "build_volume_x_mm", None) if source is not None else None)
        final_build_volume_y_mm = build_volume_y_mm or (getattr(source, "build_volume_y_mm", None) if source is not None else None)
        final_build_volume_z_mm = build_volume_z_mm or (getattr(source, "build_volume_z_mm", None) if source is not None else None)
        final_identity_key = (
            identity_key
            or (source.identity_key if source is not None else None)
            or printer_identity_key(
                name=final_name,
                host=final_host,
                port=final_port,
                protocol=final_protocol,
                service_type=final_service_type,
                evidence=source.evidence if source is not None else (),
            )
        )
        existing = None
        if source is not None and source.matched_printer_id is not None:
            existing = self._session.get(Printer, source.matched_printer_id)
        existing = existing or self.find_known_printer(
            identity_key=final_identity_key,
            host=final_host,
            port=final_port,
            protocol=final_protocol,
        )
        if existing is not None:
            self._update_known_printer_from_discovery(
                existing,
                host=final_host,
                port=final_port,
                protocol=final_protocol,
                service_type=final_service_type,
                identity_key=final_identity_key,
                state="confirmed",
                capabilities=final_capabilities,
                build_volume_x_mm=final_build_volume_x_mm,
                build_volume_y_mm=final_build_volume_y_mm,
                build_volume_z_mm=final_build_volume_z_mm,
            )
            self._session.commit()
            self._session.refresh(existing)
            return existing

        return self.create_printer(
            name=final_name,
            host=final_host,
            port=final_port,
            protocol=final_protocol,
            printer_type=final_service_type,
            build_volume_x_mm=final_build_volume_x_mm,
            build_volume_y_mm=final_build_volume_y_mm,
            build_volume_z_mm=final_build_volume_z_mm,
            state="confirmed",
            identity_key=final_identity_key,
            adapter_type=infer_adapter_type(final_service_type),
            capabilities=final_capabilities,
        )

    def delete_printer(self, printer_id: int) -> bool:
        printer = self._session.get(Printer, printer_id)
        if printer is None:
            return False
        self._session.delete(printer)
        self._session.commit()
        return True

    def save_scan_result(self, result: PrinterScanResult) -> NetworkScanRun:
        run = NetworkScanRun(
            status=result.summary.status.value,
            method=result.summary.method,
            duration_ms=result.summary.duration_ms,
            discovered_count=result.summary.discovered_count,
            scanned_host_count=result.summary.scanned_host_count,
            probe_count=result.summary.probe_count,
            raw_summary={
                "method": result.summary.method,
                "scanned_host_count": result.summary.scanned_host_count,
                "probe_count": result.summary.probe_count,
            },
        )
        self._session.add(run)
        self._session.flush()
        for printer in result.printers:
            identity_key = printer.identity_key or printer_identity_key(
                name=printer.name,
                host=printer.host,
                port=printer.port,
                protocol=printer.protocol,
                service_type=printer.service_type,
                evidence=printer.evidence,
            )
            matched_printer = self.find_known_printer(
                identity_key=identity_key,
                host=printer.host,
                port=printer.port,
                protocol=printer.protocol,
            )
            if matched_printer is not None:
                self._update_known_printer_from_discovery(
                    matched_printer,
                    host=printer.host,
                    port=printer.port,
                    protocol=printer.protocol,
                    service_type=printer.service_type,
                    identity_key=identity_key,
                    state="online",
                    capabilities=printer.capabilities,
                    build_volume_x_mm=printer.build_volume_x_mm,
                    build_volume_y_mm=printer.build_volume_y_mm,
                    build_volume_z_mm=printer.build_volume_z_mm,
                )
            self._session.add(
                NetworkScanResult(
                    scan_run_id=run.id,
                    name=printer.name,
                    host=printer.host,
                    port=printer.port,
                    protocol=printer.protocol,
                    service_type=printer.service_type,
                    identity_key=identity_key,
                    matched_printer_id=matched_printer.id if matched_printer is not None else None,
                    confidence=printer.confidence,
                    state=printer.state,
                    raw_payload={
                        "service_type": printer.service_type,
                        "confidence": printer.confidence,
                        "identity_key": identity_key,
                        "capabilities": printer.capabilities or {},
                        "build_volume": {
                            "x_mm": printer.build_volume_x_mm,
                            "y_mm": printer.build_volume_y_mm,
                            "z_mm": printer.build_volume_z_mm,
                        },
                    },
                    evidence=list(printer.evidence),
                    capabilities=printer.capabilities or {},
                    build_volume_x_mm=printer.build_volume_x_mm,
                    build_volume_y_mm=printer.build_volume_y_mm,
                    build_volume_z_mm=printer.build_volume_z_mm,
                )
            )
        self._session.commit()
        self._session.refresh(run)
        return run

    def find_known_printer(
        self,
        identity_key: str | None,
        host: str,
        port: int,
        protocol: str,
    ) -> Printer | None:
        if identity_key:
            matched = self._session.scalar(select(Printer).where(Printer.identity_key == identity_key))
            if matched is not None:
                return matched
        return self._session.scalar(
            select(Printer).where(
                Printer.host == host,
                Printer.port == port,
                Printer.protocol == protocol,
            )
        )

    def _update_known_printer_from_discovery(
        self,
        printer: Printer,
        host: str,
        port: int,
        protocol: str,
        service_type: str,
        identity_key: str | None,
        state: str,
        capabilities: dict | None = None,
        build_volume_x_mm: int | None = None,
        build_volume_y_mm: int | None = None,
        build_volume_z_mm: int | None = None,
    ) -> None:
        preserve_confirmed_endpoint = (
            state == "online"
            and identity_key is not None
            and printer.identity_key == identity_key
            and is_stable_printer_identity(identity_key)
        )
        printer.host = host
        if not preserve_confirmed_endpoint:
            printer.port = port
            printer.protocol = protocol
            printer.printer_type = service_type
            printer.adapter_type = infer_adapter_type(service_type)
            printer.capabilities = _merge_capabilities(
                capabilities_for_service_type(service_type),
                printer.capabilities,
                capabilities,
            )
        else:
            printer.capabilities = _merge_capabilities(
                printer.capabilities or capabilities_for_service_type(service_type),
                capabilities,
            )
        printer.build_volume_x_mm = build_volume_x_mm or printer.build_volume_x_mm
        printer.build_volume_y_mm = build_volume_y_mm or printer.build_volume_y_mm
        printer.build_volume_z_mm = build_volume_z_mm or printer.build_volume_z_mm
        printer.state = state
        if identity_key and printer.identity_key is None:
            printer.identity_key = identity_key


def _merge_capabilities(*sources: dict | None) -> dict:
    merged: dict = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if value is not None:
                merged[key] = value
    return merged
