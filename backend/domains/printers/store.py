from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domains.printers.entities import PrinterScanResult
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
    ) -> Printer:
        printer = Printer(
            name=name,
            host=host,
            port=port,
            protocol=protocol,
            printer_type=printer_type,
            state="manual",
            build_volume_x_mm=build_volume_x_mm,
            build_volume_y_mm=build_volume_y_mm,
            build_volume_z_mm=build_volume_z_mm,
        )
        self._session.add(printer)
        self._session.commit()
        self._session.refresh(printer)
        return printer

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
            self._session.add(
                NetworkScanResult(
                    scan_run_id=run.id,
                    name=printer.name,
                    host=printer.host,
                    port=printer.port,
                    protocol=printer.protocol,
                    service_type=printer.service_type,
                    confidence=printer.confidence,
                    state=printer.state,
                    raw_payload={"service_type": printer.service_type},
                )
            )
        self._session.commit()
        self._session.refresh(run)
        return run
