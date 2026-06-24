from __future__ import annotations

from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import create_app
from backend.core.secrets import SecretCipher
from backend.domains.printers import adapters as printer_adapters
from backend.domains.printers.adapters import (
    InvalidPrintFileError,
    MoonrakerActionResult,
    MoonrakerFile,
    capabilities_for_service_type,
    cancel_moonraker_print,
    engine_catalog,
    fetch_read_only_status,
    infer_adapter_type,
    list_moonraker_files,
    parse_moonraker_capability_diagnostics,
    parse_bambu_mqtt_status,
    parse_moonraker_job_status,
    parse_moonraker_status,
    parse_octoprint_status,
    pause_moonraker_print,
    resume_moonraker_print,
    start_moonraker_print,
    upload_moonraker_file,
)
from backend.domains.printers.credentials import (
    configure_bambu_lan_credentials,
    delete_bambu_lan_credentials,
    get_bambu_lan_access_code,
)
from backend.domains.printers.entities import DiscoveredPrinter, PrinterScanResult, PrinterScanStatus, PrinterScanSummary
from backend.domains.printers.identity import moonraker_identity_key
from backend.domains.printers.models import NetworkScanResult, NetworkScanRun, Printer
from backend.domains.printers.routes import _endpoint_capabilities, get_printer_store
from backend.domains.printers.service import (
    _detect_moonraker,
    _detect_generic_http,
    _detect_octoprint_or_prusalink,
    _limited_hosts,
    _mdns_printer_metadata,
    _moonraker_capabilities_from_objects,
    _prioritized_probe_ports,
    _probe_http_port,
    _resolve_probe_network,
    _scan_http_printers,
    merge_known_printer_discoveries,
    probe_known_printer_endpoint,
    scan_lan_for_printers,
)
from backend.domains.printers.store import PrinterStore
from backend.domains.settings.models import ProviderSecret
from backend.db.base import Base
from tests.helpers import allow_anonymous_until_bootstrap


class FakePrinter:
    id = 12
    name = "Manual MK4"
    host = "192.168.1.50"
    port = 80
    protocol = "http"
    printer_type = "prus link"
    state = "manual"
    identity_key = None
    adapter_type = None
    capabilities = {}
    credential_secret_name = None
    last_status = {}
    last_status_at = None
    build_volume_x_mm = 250
    build_volume_y_mm = 210
    build_volume_z_mm = 220


class FakeMoonrakerPrinter(FakePrinter):
    name = "Snapmaker U1"
    host = "192.168.1.80"
    port = 7125
    protocol = "http"
    printer_type = "http_probe:snapmaker_moonraker"
    adapter_type = "moonraker"
    capabilities = capabilities_for_service_type("http_probe:snapmaker_moonraker")


class FakeLegacyMoonrakerPrinter(FakeMoonrakerPrinter):
    capabilities = {
        "adapter": "moonraker",
        "read_only_status": True,
        "safe_endpoints": ["/server/info", "/printer/info", "/printer/objects/list"],
        "control_enabled": False,
    }


class FakeBambuMqttPrinter(FakePrinter):
    name = "Bambu A1"
    host = "192.168.1.53"
    port = 8883
    protocol = "mqtts"
    printer_type = "mqtt_probe:bambu_mqtt"
    adapter_type = "bambu_mqtt"
    capabilities = capabilities_for_service_type("mqtt_probe:bambu_mqtt")


class FakePrinterStore:
    def __init__(self, printer=None):
        self.printer = printer or FakePrinter()

    def list_printers(self):
        return [self.printer]

    def create_printer(
        self,
        name,
        host,
        port,
        protocol="http",
        printer_type="unknown",
        build_volume_x_mm=None,
        build_volume_y_mm=None,
        build_volume_z_mm=None,
    ):
        printer = FakePrinter()
        printer.name = name
        printer.host = host
        printer.port = port
        printer.protocol = protocol
        printer.printer_type = printer_type
        printer.build_volume_x_mm = build_volume_x_mm
        printer.build_volume_y_mm = build_volume_y_mm
        printer.build_volume_z_mm = build_volume_z_mm
        return printer

    def confirm_discovered_printer(
        self,
        name,
        host,
        port,
        protocol,
        service_type,
        identity_key=None,
        capabilities=None,
        build_volume_x_mm=None,
        build_volume_y_mm=None,
        build_volume_z_mm=None,
        scan_result_id=None,
    ):
        printer = FakePrinter()
        printer.name = name
        printer.host = host
        printer.port = port
        printer.protocol = protocol
        printer.printer_type = service_type
        printer.state = "confirmed"
        printer.adapter_type = "moonraker" if "moonraker" in service_type else None
        printer.capabilities = capabilities or {"read_only_status": printer.adapter_type is not None}
        printer.build_volume_x_mm = build_volume_x_mm
        printer.build_volume_y_mm = build_volume_y_mm
        printer.build_volume_z_mm = build_volume_z_mm
        return printer

    def delete_printer(self, printer_id):
        return printer_id == 12

    def save_scan_result(self, result):
        run = NetworkScanRun()
        run.id = 44
        return run


class FakeSession:
    def __init__(self, known_printer=None, scan_results=None):
        self.added = []
        self.committed = False
        self.known_printer = known_printer
        self.scan_results = scan_results or {}

    def add(self, item):
        self.added.append(item)

    def flush(self):
        for item in self.added:
            if isinstance(item, NetworkScanRun):
                item.id = 55

    def commit(self):
        self.committed = True

    def refresh(self, item):
        return None

    def get(self, model, item_id):
        if model is Printer and self.known_printer is not None and self.known_printer.id == item_id:
            return self.known_printer
        if model is NetworkScanResult:
            return self.scan_results.get(item_id)
        return None

    def scalar(self, statement):
        _ = statement
        return self.known_printer


def test_printer_models_are_registered():
    table_names = set(Base.metadata.tables)

    assert Printer.__tablename__ in table_names
    assert NetworkScanRun.__tablename__ in table_names
    assert NetworkScanResult.__tablename__ in table_names
    assert "scanned_host_count" in NetworkScanRun.__table__.columns
    assert "probe_count" in NetworkScanRun.__table__.columns
    assert "identity_key" in Printer.__table__.columns
    assert "identity_key" in NetworkScanResult.__table__.columns
    assert "matched_printer_id" in NetworkScanResult.__table__.columns
    assert "capabilities" in NetworkScanResult.__table__.columns
    assert "build_volume_x_mm" in NetworkScanResult.__table__.columns
    assert "build_volume_y_mm" in NetworkScanResult.__table__.columns
    assert "build_volume_z_mm" in NetworkScanResult.__table__.columns


def test_printer_api_lists_and_adds_printers():
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore()
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    list_response = client.get("/api/printers")
    add_response = client.post("/api/printers", json={"name": "Manual MK4", "host": "192.168.1.50", "port": 80})
    delete_response = client.delete("/api/printers/12")

    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "Manual MK4"
    assert list_response.json()[0]["build_volume_x_mm"] == 250
    assert add_response.status_code == 200
    assert add_response.json()["host"] == "192.168.1.50"
    assert delete_response.status_code == 204


def test_printer_api_confirms_discovered_candidate():
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore()
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post(
        "/api/printers/confirm-discovered",
        json={
            "name": "Moonraker at 192.168.1.44:7125",
            "host": "192.168.1.44",
            "port": 7125,
            "protocol": "http",
            "service_type": "http_probe:moonraker",
            "confidence": 92,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "confirmed"
    assert body["adapter_type"] == "moonraker"


def test_moonraker_file_and_print_routes_call_safe_adapter_functions(monkeypatch):
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore(FakeMoonrakerPrinter())
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)
    calls = []

    def fake_job_status(printer):
        from datetime import UTC, datetime

        from backend.domains.printers.adapters import MoonrakerJobStatus

        calls.append(("status", printer.id))
        return MoonrakerJobStatus(
            state="printing",
            filename="cube.gcode",
            progress=0.5,
            message=None,
            raw_status={"result": {"status": {}}},
            observed_at=datetime.now(UTC),
        )

    def fake_files(printer):
        calls.append(("files", printer.id))
        return [MoonrakerFile(path="cube.gcode", size=100, modified=1.0, permissions="rw")]

    def fake_upload(printer, filename, content, content_type=None):
        calls.append(("upload", filename, content, content_type))
        return MoonrakerActionResult(action="upload", accepted=True, raw_response={"ok": True})

    def fake_start(printer, filename):
        calls.append(("start", filename))
        return MoonrakerActionResult(action="start", accepted=True, raw_response="ok")

    def fake_pause(printer):
        calls.append(("pause", printer.id))
        return MoonrakerActionResult(action="pause", accepted=True, raw_response="ok")

    monkeypatch.setattr("backend.domains.printers.routes.fetch_moonraker_job_status", fake_job_status)
    monkeypatch.setattr("backend.domains.printers.routes.list_moonraker_files", fake_files)
    monkeypatch.setattr("backend.domains.printers.routes.upload_moonraker_file", fake_upload)
    monkeypatch.setattr("backend.domains.printers.routes.start_moonraker_print", fake_start)
    monkeypatch.setattr("backend.domains.printers.routes.pause_moonraker_print", fake_pause)

    status_response = client.get("/api/printers/12/job-status")
    files_response = client.get("/api/printers/12/files")
    upload_response = client.post(
        "/api/printers/12/files",
        files={"file": ("cube.gcode", b"G1 X1", "application/octet-stream")},
    )
    start_response = client.post("/api/printers/12/print/start", json={"filename": "cube.gcode"})
    pause_response = client.post("/api/printers/12/print/pause")

    assert status_response.status_code == 200
    assert status_response.json()["filename"] == "cube.gcode"
    assert files_response.status_code == 200
    assert files_response.json()[0]["path"] == "cube.gcode"
    assert upload_response.status_code == 201
    assert start_response.json()["action"] == "start"
    assert pause_response.json()["action"] == "pause"
    assert ("upload", "cube.gcode", b"G1 X1", "application/octet-stream") in calls


def test_moonraker_job_status_normalizes_thermals_and_tool_colors():
    status = parse_moonraker_job_status(
        {
            "result": {
                "status": {
                    "print_stats": {"state": "printing", "filename": "cube.gcode", "message": "Printing"},
                    "virtual_sdcard": {"progress": 0.5},
                    "heater_bed": {"temperature": 61.2, "target": 65.0, "power": 0.4},
                    "extruder": {"temperature": 211.4, "target": 215.0, "power": 0.33, "filament_color": "#ff0000"},
                    "extruder1": {"temperature": 209.8, "target": 215.0, "material": {"color": "#00ff00"}},
                    "extruder2": {"temperature": 35.0, "target": 0.0},
                    "extruder3": {"temperature": 34.5, "target": 0.0},
                }
            }
        },
        capabilities={"toolheads": [{"index": 2, "color": "#0000ff"}, {"index": 3, "filament_color": "#ffffff"}]},
    )

    assert status.state == "printing"
    assert status.filename == "cube.gcode"
    assert status.progress == 0.5
    assert status.bed_temperature is not None
    assert status.bed_temperature.current_c == 61.2
    assert status.bed_temperature.target_c == 65.0
    assert [toolhead.label for toolhead in status.toolheads] == ["T0", "T1", "T2", "T3"]
    assert status.toolheads[0].current_temperature is not None
    assert status.toolheads[0].current_temperature.current_c == 211.4
    assert [toolhead.color for toolhead in status.toolheads] == ["#ff0000", "#00ff00", "#0000ff", "#ffffff"]
    assert [toolhead.color_source for toolhead in status.toolheads] == [
        "moonraker_object",
        "moonraker_object",
        "saved_capabilities",
        "saved_capabilities",
    ]


def test_printer_job_status_response_includes_moonraker_telemetry(monkeypatch):
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore(FakeMoonrakerPrinter())
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    def fake_job_status(printer):
        from datetime import UTC, datetime

        from backend.domains.printers.adapters import MoonrakerJobStatus, MoonrakerTemperature, MoonrakerToolheadTelemetry

        assert printer.id == 12
        return MoonrakerJobStatus(
            state="printing",
            filename="cube.gcode",
            progress=0.25,
            message=None,
            raw_status={"result": {"status": {}}},
            observed_at=datetime.now(UTC),
            bed_temperature=MoonrakerTemperature(current_c=60.0, target_c=65.0),
            toolheads=(
                MoonrakerToolheadTelemetry(
                    name="extruder",
                    label="T0",
                    index=0,
                    current_temperature=MoonrakerTemperature(current_c=210.0, target_c=215.0),
                    color="#ff0000",
                    color_source="moonraker_object",
                    material="PLA",
                    material_source="vendor_object",
                    vendor="Snapmaker",
                    subtype="SnapSpeed",
                ),
            ),
        )

    monkeypatch.setattr("backend.domains.printers.routes.fetch_moonraker_job_status", fake_job_status)

    response = client.get("/api/printers/12/job-status")

    assert response.status_code == 200
    body = response.json()
    assert body["bed_temperature"] == {"current_c": 60.0, "target_c": 65.0, "power": None}
    assert body["toolheads"][0]["label"] == "T0"
    assert body["toolheads"][0]["current_temperature"]["current_c"] == 210.0
    assert body["toolheads"][0]["color"] == "#ff0000"
    assert body["toolheads"][0]["color_source"] == "moonraker_object"
    assert body["toolheads"][0]["material"] == "PLA"
    assert body["toolheads"][0]["material_source"] == "vendor_object"
    assert body["toolheads"][0]["vendor"] == "Snapmaker"
    assert body["toolheads"][0]["subtype"] == "SnapSpeed"


def test_moonraker_job_status_maps_snapmaker_u1_filament_slots():
    status = parse_moonraker_job_status(
        {
            "result": {
                "status": {
                    "print_stats": {"state": "standby"},
                    "extruder": {"temperature": 28.0, "target": 0.0},
                    "extruder1": {"temperature": 28.0, "target": 0.0},
                    "extruder2": {"temperature": 29.0, "target": 0.0},
                    "extruder3": {"temperature": 29.0, "target": 0.0},
                    "filament_detect": {
                        "info": [
                            {
                                "MAIN_TYPE": "NONE",
                                "MANUFACTURER": "NONE",
                                "VENDOR": "NONE",
                                "ARGB_COLOR": 4294967295,
                                "RGB_1": 16777215,
                            },
                            {
                                "MAIN_TYPE": "PLA",
                                "MANUFACTURER": "Polymaker",
                                "VENDOR": "Snapmaker",
                                "SUB_TYPE": "SnapSpeed",
                                "ARGB_COLOR": 4278716941,
                                "RGB_1": 526861,
                            },
                            {
                                "MAIN_TYPE": "PLA",
                                "MANUFACTURER": "Polymaker",
                                "VENDOR": "Snapmaker",
                                "SUB_TYPE": "SnapSpeed",
                                "ARGB_COLOR": 4293058267,
                                "RGB_1": 14868187,
                            },
                            {
                                "MAIN_TYPE": "PLA",
                                "MANUFACTURER": "Polymaker",
                                "VENDOR": "Snapmaker",
                                "SUB_TYPE": "SnapSpeed",
                                "ARGB_COLOR": 4293340957,
                                "RGB_1": 15150877,
                            },
                        ]
                    },
                    "filament_feed left": {
                        "extruder0": {"filament_detected": True},
                        "extruder1": {"filament_detected": True},
                    },
                    "filament_feed right": {
                        "extruder2": {"filament_detected": True},
                        "extruder3": {"filament_detected": True},
                    },
                    "gcode_macro _FILAMENT_FEED_VARIABLE": {"module_sequence": ["left", "left", "right", "right"]},
                }
            }
        }
    )

    assert [toolhead.label for toolhead in status.toolheads] == ["T0", "T1", "T2", "T3"]
    assert [toolhead.color for toolhead in status.toolheads] == [None, "#080a0d", "#e2dedb", "#e72f1d"]
    assert [toolhead.color_source for toolhead in status.toolheads] == [None, "vendor_object", "vendor_object", "vendor_object"]
    assert [toolhead.material for toolhead in status.toolheads] == [None, "PLA", "PLA", "PLA"]
    assert [toolhead.vendor for toolhead in status.toolheads] == [None, "Snapmaker", "Snapmaker", "Snapmaker"]
    assert [toolhead.subtype for toolhead in status.toolheads] == [None, "SnapSpeed", "SnapSpeed", "SnapSpeed"]


def test_moonraker_job_status_uses_spoolman_for_single_toolhead_metadata():
    status = parse_moonraker_job_status(
        {
            "result": {
                "status": {
                    "print_stats": {"state": "standby"},
                    "extruder": {"temperature": 28.0, "target": 0.0},
                    "spoolman": {"spoolman_connected": True, "spool_id": 2},
                    "spoolman_active_spool": {
                        "response": {
                            "id": 2,
                            "filament": {
                                "material": "PLA",
                                "vendor": {"name": "Fusion"},
                                "color_hex": "BD0B0B",
                            },
                        },
                        "error": None,
                    },
                }
            }
        }
    )

    assert len(status.toolheads) == 1
    assert status.toolheads[0].color == "#bd0b0b"
    assert status.toolheads[0].color_source == "spoolman"
    assert status.toolheads[0].material == "PLA"
    assert status.toolheads[0].material_source == "spoolman"
    assert status.toolheads[0].vendor == "Fusion"


def test_printer_engine_catalog_can_refresh_without_restarting_web():
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore(FakeMoonrakerPrinter())
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    list_response = client.get("/api/printers/engines")
    refresh_response = client.post("/api/printers/engines/refresh")

    assert any(engine["engine_id"] == "moonraker" for engine in engine_catalog())
    assert list_response.status_code == 200
    assert refresh_response.status_code == 200
    assert refresh_response.json()[0]["engine_id"] == "moonraker"
    assert refresh_response.json()[0]["capabilities"]["control_enabled"] is True
    assert refresh_response.json()[0]["capabilities"]["telemetry_source_priority"] == [
        "moonraker_object",
        "vendor_object",
        "spoolman",
        "extension_agent",
        "saved_capabilities",
    ]
    assert any(engine["engine_id"] == "bambu_mqtt" for engine in refresh_response.json())


def test_bambu_mqtt_engine_catalog_and_status_are_read_only():
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore(FakeBambuMqttPrinter())
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    engines_response = client.get("/api/printers/engines")
    status_response = client.get("/api/printers/12/status")

    bambu_engine = next(engine for engine in engines_response.json() if engine["engine_id"] == "bambu_mqtt")
    assert infer_adapter_type("mqtt_probe:bambu_mqtt") == "bambu_mqtt"
    assert bambu_engine["capabilities"]["control_enabled"] is False
    assert bambu_engine["capabilities"]["credential_required"] is True
    assert bambu_engine["capabilities"]["pushall_min_interval_seconds"] == 300
    assert status_response.status_code == 200
    assert status_response.json()["adapter_type"] == "bambu_mqtt"
    assert status_response.json()["state"] == "credentials_required"
    assert status_response.json()["raw_status"]["control_enabled"] is False


def test_bambu_mqtt_status_remains_read_only_when_live_access_code_is_missing():
    printer = FakeBambuMqttPrinter()
    printer.credential_secret_name = "printer-12-bambu-lan"
    printer.capabilities = {**printer.capabilities, "device_id": "00M00A000000000", "control_enabled": True}

    status = fetch_read_only_status(printer)

    assert status.adapter_type == "bambu_mqtt"
    assert status.state == "telemetry_unavailable"
    assert status.raw_status["credential_configured"] is True
    assert status.raw_status["device_id_configured"] is True
    assert status.capabilities["control_enabled"] is False
    assert status.capabilities["telemetry_source_priority"] == ["bambu_mqtt_report", "saved_capabilities"]


def test_bambu_mqtt_status_normalizes_report_without_exposing_access_code(monkeypatch):
    printer = FakeBambuMqttPrinter()
    printer.credential_secret_name = "printer-12-bambu-lan"
    printer.capabilities = {**printer.capabilities, "device_id": "00M00A000000000"}
    calls = []

    def fake_report(printer_arg, device_id, access_code, timeout_seconds=2.0):
        calls.append((printer_arg.id, device_id, access_code, timeout_seconds))
        return _bambu_report_payload()

    monkeypatch.setattr(printer_adapters, "fetch_bambu_mqtt_report", fake_report)

    status = fetch_read_only_status(printer, api_key="12345678", timeout_seconds=1.5)

    assert calls == [(printer.id, "00M00A000000000", "12345678", 1.5)]
    assert status.state == "printing"
    assert status.raw_status["job"]["progress"] == 42.0
    assert status.raw_status["temperatures"]["nozzle_current_c"] == 219.5
    assert status.raw_status["ams"]["active_tray"] == "1"
    assert status.raw_status["ams"]["trays"][1]["active"] is True
    assert status.raw_status["ams"]["trays"][1]["color"] == "#ff3300"
    assert "12345678" not in str(status.raw_status)
    assert status.raw_status["control_enabled"] is False


def test_bambu_mqtt_report_parser_maps_job_temperatures_ams_and_errors():
    status = parse_bambu_mqtt_status(_bambu_report_payload())

    assert status.state == "printing"
    assert status.raw_status["job"]["filename"] == "benchy.3mf"
    assert status.raw_status["job"]["remaining_minutes"] == 33.0
    assert status.raw_status["temperatures"]["bed_target_c"] == 60.0
    assert status.raw_status["ams"]["trays"][0]["material"] == "PLA"
    assert status.raw_status["ams"]["trays"][1]["subtype"] == "Bambu PLA Matte"
    assert status.raw_status["errors"]["hms"] == [{"code": "0300_4000"}]


def test_bambu_lan_credentials_are_encrypted_and_printer_scoped():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_sqlite_printer_credential_tables(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    cipher = SecretCipher("2bfxMfuhQ9gjY4BfevPBknojr1mweViuOa3UccQuXIk=")
    with SessionLocal() as session:
        printer = Printer(
            id=42,
            name="Bambu A1",
            host="192.168.1.53",
            port=8883,
            protocol="mqtts",
            printer_type="mqtt_probe:bambu_mqtt",
            state="confirmed",
            adapter_type="bambu_mqtt",
            capabilities=capabilities_for_service_type("mqtt_probe:bambu_mqtt"),
        )
        session.add(printer)
        session.commit()

        updated = configure_bambu_lan_credentials(session, cipher, printer, "12345678", "00M00A000000000")

        assert updated.credential_secret_name == "printer_42_bambu_lan"
        assert updated.capabilities["device_id"] == "00M00A000000000"
        assert get_bambu_lan_access_code(session, cipher, updated) == "12345678"
        secret_record = session.query(ProviderSecret).one()
        assert "12345678" not in secret_record.encrypted_value
        assert secret_record.last_four == "5678"

        assert delete_bambu_lan_credentials(session, updated) is True
        assert updated.credential_secret_name is None
        assert get_bambu_lan_access_code(session, cipher, updated) is None


def _create_sqlite_printer_credential_tables(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE printers (
                id INTEGER PRIMARY KEY,
                owner_user_id INTEGER,
                name VARCHAR(160) NOT NULL,
                host VARCHAR(255) NOT NULL,
                port INTEGER NOT NULL,
                protocol VARCHAR(40) NOT NULL,
                printer_type VARCHAR(80) NOT NULL,
                state VARCHAR(40) NOT NULL,
                identity_key VARCHAR(255),
                adapter_type VARCHAR(80),
                capabilities JSON NOT NULL,
                credential_secret_name VARCHAR(120),
                last_status JSON NOT NULL DEFAULT '{}',
                last_status_at DATETIME,
                build_volume_x_mm INTEGER,
                build_volume_y_mm INTEGER,
                build_volume_z_mm INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE provider_secrets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider VARCHAR(40) NOT NULL,
                secret_name VARCHAR(80) NOT NULL,
                encrypted_value TEXT NOT NULL,
                encryption_key_id VARCHAR(64) NOT NULL,
                secret_fingerprint VARCHAR(64) NOT NULL,
                last_four VARCHAR(8) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                CONSTRAINT uq_provider_secrets_provider_secret_name UNIQUE (provider, secret_name)
            )
            """
        )


def _bambu_report_payload():
    return {
        "print": {
            "gcode_state": "RUNNING",
            "gcode_file": "benchy.3mf",
            "mc_percent": 42,
            "mc_remaining_time": 33,
            "nozzle_temper": 219.5,
            "nozzle_target_temper": 220,
            "bed_temper": 59.1,
            "bed_target_temper": 60,
            "ams": {
                "tray_now": "1",
                "ams": [
                    {
                        "tray": [
                            {"id": "0", "tray_color": "00AAFFFF", "tray_type": "PLA"},
                            {
                                "id": "1",
                                "tray_color": "FF3300FF",
                                "tray_type": "PLA",
                                "tray_sub_brands": "Bambu PLA Matte",
                            },
                        ]
                    }
                ],
            },
            "hms": [{"code": "0300_4000"}],
        }
    }


def test_moonraker_capability_diagnostics_parses_optional_integrations():
    diagnostics = parse_moonraker_capability_diagnostics(
        extensions_payload={
            "result": {
                "agents": [
                    {"name": "moonagent", "version": "0.0.1", "type": "agent", "url": "https://example.test/agent"}
                ]
            }
        },
        spoolman_payload={"result": {"spoolman_connected": True, "spool_id": 2, "pending_reports": []}},
    )

    assert diagnostics.extension_agents_available is True
    assert diagnostics.extension_agents[0]["name"] == "moonagent"
    assert diagnostics.spoolman_available is True
    assert diagnostics.spoolman_status == {"spoolman_connected": True, "spool_id": 2, "pending_reports": []}
    assert diagnostics.probe_errors == {}


def test_moonraker_capability_diagnostics_treats_missing_spoolman_as_nonfatal():
    diagnostics = parse_moonraker_capability_diagnostics(
        extensions_payload={"result": {"agents": []}},
        spoolman_payload={"error": {"code": 404, "message": "Not Found"}},
        probe_errors={"spoolman": "not_configured"},
    )

    assert diagnostics.extension_agents_available is False
    assert diagnostics.extension_agents == ()
    assert diagnostics.spoolman_available is False
    assert diagnostics.spoolman_status is None
    assert diagnostics.probe_errors == {"spoolman": "not_configured"}


def test_printer_capability_diagnostics_route_serializes_probe_results(monkeypatch):
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore(FakeMoonrakerPrinter())
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    def fake_diagnostics(printer):
        from datetime import UTC, datetime

        from backend.domains.printers.adapters import MoonrakerCapabilityDiagnostics

        assert printer.id == 12
        return MoonrakerCapabilityDiagnostics(
            adapter_type="moonraker",
            extension_agents_available=True,
            extension_agents=({"name": "moonagent", "version": "1.0", "type": "agent", "url": "https://example.test"},),
            spoolman_available=False,
            spoolman_status=None,
            probe_errors={"spoolman": "not_configured"},
            observed_at=datetime.now(UTC),
        )

    monkeypatch.setattr("backend.domains.printers.routes.fetch_moonraker_capability_diagnostics", fake_diagnostics)

    response = client.get("/api/printers/12/capability-diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["extension_agents_available"] is True
    assert body["extension_agents"][0]["name"] == "moonagent"
    assert body["spoolman_available"] is False
    assert body["probe_errors"] == {"spoolman": "not_configured"}


def test_printer_extension_request_route_requires_allowlisted_method(monkeypatch):
    class FakeExtensionPrinter(FakeMoonrakerPrinter):
        capabilities = {
            **FakeMoonrakerPrinter.capabilities,
            "moonraker_extension_methods": [{"agent": "moonagent", "method": "moonagent.status"}],
        }

    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore(FakeExtensionPrinter())
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    def fake_request(printer, agent, method, arguments=None):
        from backend.domains.printers.adapters import MoonrakerExtensionResult

        assert printer.id == 12
        assert agent == "moonagent"
        assert method == "moonagent.status"
        assert arguments == {"detail": True}
        return MoonrakerExtensionResult(
            agent=agent,
            method=method,
            accepted=True,
            raw_response={"result": {"ok": True}},
        )

    monkeypatch.setattr("backend.domains.printers.routes.request_moonraker_extension", fake_request)

    response = client.post(
        "/api/printers/12/extensions/request",
        json={"agent": "moonagent", "method": "moonagent.status", "arguments": {"detail": True}},
    )

    assert response.status_code == 200
    assert response.json()["agent"] == "moonagent"
    assert response.json()["method"] == "moonagent.status"
    assert response.json()["raw_response"] == {"result": {"ok": True}}


def test_printer_extension_request_route_rejects_non_allowlisted_method():
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore(FakeMoonrakerPrinter())
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.post(
        "/api/printers/12/extensions/request",
        json={"agent": "moonagent", "method": "moonagent.status", "arguments": {}},
    )

    assert response.status_code == 403
    assert "allowlisted" in response.json()["detail"]


def test_moonraker_routes_reject_unsupported_printers():
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore(FakePrinter())
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)

    response = client.get("/api/printers/12/files")

    assert response.status_code == 409
    assert "Moonraker file and job controls" in response.json()["detail"]


def test_moonraker_routes_accept_legacy_read_only_capabilities(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def get(self, url, params=None):
            _ = url, params
            return FakeResponse([{"path": "legacy.gcode", "size": 100, "modified": 1.0, "permissions": "rw"}])

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore(FakeLegacyMoonrakerPrinter())
    allow_anonymous_until_bootstrap(app)
    client = TestClient(app)
    monkeypatch.setattr("backend.domains.printers.adapters.httpx.Client", FakeClient)

    response = client.get("/api/printers/12/files")

    assert response.status_code == 200
    assert response.json()[0]["path"] == "legacy.gcode"


def test_printer_scan_groups_services_by_host(monkeypatch):
    def fake_scan_lan_for_printers(**kwargs):
        return PrinterScanResult(
            summary=PrinterScanSummary(
                status=PrinterScanStatus.COMPLETED,
                duration_ms=250,
                discovered_count=2,
                method="combined",
                scanned_host_count=1,
                probe_count=3,
            ),
            printers=(
                DiscoveredPrinter(
                    name="Snapmaker U1 Moonraker at 192.168.1.44:7125",
                    host="192.168.1.44",
                    port=7125,
                    protocol="http",
                    service_type="http_probe:snapmaker_moonraker",
                    confidence=94,
                    evidence=("Read-only HTTP probe matched http_probe:snapmaker_moonraker",),
                ),
                DiscoveredPrinter(
                    name="Moonraker at 192.168.1.44:80",
                    host="192.168.1.44",
                    port=80,
                    protocol="http",
                    service_type="http_probe:moonraker",
                    confidence=92,
                    evidence=("Read-only HTTP probe matched http_probe:moonraker",),
                ),
            ),
        )

    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore()
    allow_anonymous_until_bootstrap(app)
    monkeypatch.setattr("backend.domains.printers.routes.scan_lan_for_printers", fake_scan_lan_for_printers)
    client = TestClient(app)

    response = client.post("/api/printers/scan", json={})

    assert response.status_code == 200
    group = response.json()["groups"][0]
    assert group["host"] == "192.168.1.44"
    assert group["inferred_type"] == "Snapmaker / Moonraker"
    assert group["ports"] == [80, 7125]
    assert "Klipper-compatible status" in group["capabilities"]
    assert "Klipper/Moonraker API" in group["capabilities"]
    assert len(group["endpoints"]) == 2
    assert "Read-only HTTP probe matched http_probe:snapmaker_moonraker" in group["endpoints"][0]["evidence"]


def test_printer_store_persists_scan_metrics_and_results():
    result = PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=100,
            discovered_count=1,
            method="mdns",
            scanned_host_count=0,
            probe_count=4,
        ),
        printers=(
            DiscoveredPrinter(
                name="OctoPrint",
                host="192.168.1.60",
                port=80,
                protocol="http",
                service_type="_octoprint._tcp.local.",
                confidence=90,
            ),
        ),
    )
    session = FakeSession()

    run = PrinterStore(session).save_scan_result(result)

    assert run.id == 55
    assert session.committed is True
    assert any(isinstance(item, NetworkScanRun) for item in session.added)
    assert any(isinstance(item, NetworkScanResult) for item in session.added)


def test_printer_store_persists_scan_capabilities_and_build_volume():
    result = PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=100,
            discovered_count=1,
            method="http_probe",
            scanned_host_count=1,
            probe_count=1,
        ),
        printers=(
            DiscoveredPrinter(
                name="Snapmaker U1 Moonraker",
                host="192.168.1.80",
                port=7125,
                protocol="http",
                service_type="http_probe:snapmaker_moonraker",
                confidence=94,
                capabilities={"adapter": "moonraker", "toolhead_count": 4, "color_count": 4},
                build_volume_x_mm=320,
                build_volume_y_mm=320,
                build_volume_z_mm=320,
            ),
        ),
    )
    session = FakeSession()

    PrinterStore(session).save_scan_result(result)

    saved_result = next(item for item in session.added if isinstance(item, NetworkScanResult))
    assert saved_result.capabilities["toolhead_count"] == 4
    assert saved_result.capabilities["color_count"] == 4
    assert saved_result.build_volume_x_mm == 320
    assert saved_result.raw_payload["build_volume"]["x_mm"] == 320


def test_confirm_discovered_printer_inherits_persisted_scan_capabilities():
    source = NetworkScanResult(
        id=5,
        scan_run_id=1,
        name="Snapmaker U1 Moonraker",
        host="192.168.1.80",
        port=7125,
        protocol="http",
        service_type="http_probe:snapmaker_moonraker",
        identity_key="moonraker:snapmaker:machine_id:u1",
        confidence=94,
        evidence=["Read-only Moonraker object query exposed deterministic capability metadata"],
        capabilities={"adapter": "moonraker", "toolhead_count": 4, "color_count": 4},
        build_volume_x_mm=320,
        build_volume_y_mm=320,
        build_volume_z_mm=320,
    )
    session = FakeSession(scan_results={source.id: source})

    printer = PrinterStore(session).confirm_discovered_printer(
        name="Snapmaker U1",
        host="192.168.1.80",
        port=7125,
        protocol="http",
        service_type="http_probe:snapmaker_moonraker",
        scan_result_id=source.id,
    )

    assert printer.capabilities["toolhead_count"] == 4
    assert printer.capabilities["color_count"] == 4
    assert printer.build_volume_x_mm == 320
    assert printer.build_volume_y_mm == 320
    assert printer.build_volume_z_mm == 320


def test_scan_refresh_preserves_manual_build_volume_when_scan_does_not_prove_it():
    known = Printer(
        id=10,
        name="Manual U1",
        host="192.168.1.80",
        port=7125,
        protocol="http",
        printer_type="http_probe:snapmaker_moonraker",
        state="confirmed",
        identity_key="moonraker:snapmaker:machine_id:u1",
        capabilities={"adapter": "moonraker", "toolhead_count": 4},
        build_volume_x_mm=320,
        build_volume_y_mm=320,
        build_volume_z_mm=320,
    )
    result = PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=100,
            discovered_count=1,
            method="http_probe",
            scanned_host_count=1,
            probe_count=1,
        ),
        printers=(
            DiscoveredPrinter(
                name="Snapmaker U1 Moonraker",
                host="192.168.1.81",
                port=7125,
                protocol="http",
                service_type="http_probe:snapmaker_moonraker",
                confidence=94,
                identity_key=known.identity_key,
                capabilities={"adapter": "moonraker"},
            ),
        ),
    )
    session = FakeSession(known_printer=known)

    PrinterStore(session).save_scan_result(result)

    assert known.build_volume_x_mm == 320
    assert known.build_volume_y_mm == 320
    assert known.build_volume_z_mm == 320
    assert known.capabilities["toolhead_count"] == 4


def test_known_printer_endpoint_is_added_when_generic_scan_misses_it(monkeypatch):
    known = Printer(
        id=10,
        name="Snapmaker U1",
        host="192.168.1.80",
        port=7125,
        protocol="http",
        printer_type="http_probe:snapmaker_moonraker",
        state="confirmed",
        identity_key="moonraker:snapmaker:machine_id:u1",
        capabilities={"adapter": "moonraker", "toolhead_count": 4, "color_count": 4},
        build_volume_x_mm=320,
        build_volume_y_mm=320,
        build_volume_z_mm=320,
    )
    result = PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=100,
            discovered_count=0,
            method="combined",
            scanned_host_count=254,
            probe_count=2540,
        ),
        printers=(),
    )

    def fake_probe(printer, timeout_seconds=1.0):
        assert printer is known
        assert timeout_seconds == 0.5
        return DiscoveredPrinter(
            name="Snapmaker U1",
            host="192.168.1.80",
            port=7125,
            protocol="http",
            service_type="http_probe:snapmaker_moonraker",
            confidence=76,
            state="known",
            evidence=("Configured printer endpoint http://192.168.1.80:7125 is reachable",),
            identity_key=known.identity_key,
            matched_printer_id=known.id,
            capabilities=known.capabilities,
            build_volume_x_mm=known.build_volume_x_mm,
            build_volume_y_mm=known.build_volume_y_mm,
            build_volume_z_mm=known.build_volume_z_mm,
        )

    monkeypatch.setattr("backend.domains.printers.service.probe_known_printer_endpoint", fake_probe)

    merged = merge_known_printer_discoveries(result, [known], timeout_seconds=0.5)

    assert merged.summary.discovered_count == 1
    assert merged.summary.probe_count == 2541
    assert merged.printers[0].matched_printer_id == known.id
    assert merged.printers[0].capabilities["toolhead_count"] == 4
    assert merged.printers[0].build_volume_x_mm == 320


def test_known_printer_endpoint_is_not_duplicated_when_scan_finds_it(monkeypatch):
    known = Printer(
        id=10,
        name="Snapmaker U1",
        host="192.168.1.80",
        port=7125,
        protocol="http",
        printer_type="http_probe:snapmaker_moonraker",
        state="confirmed",
        identity_key="moonraker:snapmaker:machine_id:u1",
    )
    result = PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=100,
            discovered_count=1,
            method="combined",
            scanned_host_count=254,
            probe_count=2540,
        ),
        printers=(
            DiscoveredPrinter(
                name="Snapmaker U1 Moonraker",
                host=known.host,
                port=known.port,
                protocol=known.protocol,
                service_type="http_probe:snapmaker_moonraker",
                confidence=94,
                identity_key=known.identity_key,
            ),
        ),
    )

    def fail_probe(printer, timeout_seconds=1.0):
        raise AssertionError("known endpoint probe should not run for already discovered printer")

    monkeypatch.setattr("backend.domains.printers.service.probe_known_printer_endpoint", fail_probe)

    merged = merge_known_printer_discoveries(result, [known], timeout_seconds=0.5)

    assert merged is result
    assert len(merged.printers) == 1


def test_known_printer_endpoint_fallback_carries_stored_metadata(monkeypatch):
    known = Printer(
        id=10,
        name="Snapmaker U1",
        host="192.168.1.80",
        port=7125,
        protocol="http",
        printer_type="http_probe:snapmaker_moonraker",
        state="confirmed",
        identity_key="moonraker:snapmaker:machine_id:u1",
        capabilities={"adapter": "moonraker", "toolhead_count": 4, "color_count": 4},
        build_volume_x_mm=320,
        build_volume_y_mm=320,
        build_volume_z_mm=320,
    )
    monkeypatch.setattr("backend.domains.printers.service._probe_http_port", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda *args, **kwargs: True)

    discovered = probe_known_printer_endpoint(known, timeout_seconds=0.5)

    assert discovered is not None
    assert discovered.name == "Snapmaker U1"
    assert discovered.service_type == "http_probe:snapmaker_moonraker"
    assert discovered.state == "known"
    assert discovered.confidence == 76
    assert discovered.matched_printer_id == known.id
    assert discovered.identity_key == known.identity_key
    assert discovered.capabilities["toolhead_count"] == 4
    assert discovered.capabilities["color_count"] == 4
    assert discovered.build_volume_x_mm == 320
    assert "Configured printer host is reachable at http://192.168.1.80:7125" in discovered.evidence


def test_known_printer_endpoint_fallback_checks_standard_ports_on_known_host(monkeypatch):
    known = Printer(
        id=10,
        name="Snapmaker U1",
        host="192.168.1.80",
        port=7125,
        protocol="http",
        printer_type="http_probe:snapmaker_moonraker",
        state="confirmed",
        identity_key="moonraker:snapmaker:machine_id:u1",
        capabilities={"adapter": "moonraker", "toolhead_count": 4},
    )
    checked_ports = []

    def fake_tcp_open(host, port, timeout_seconds):
        checked_ports.append(port)
        return port == 80

    monkeypatch.setattr("backend.domains.printers.service._probe_http_port", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.domains.printers.service._probe_bambu_mqtt_port", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", fake_tcp_open)

    discovered = probe_known_printer_endpoint(known, timeout_seconds=1.5)

    assert discovered is not None
    assert discovered.host == "192.168.1.80"
    assert discovered.port == 80
    assert discovered.protocol == "http"
    assert discovered.matched_printer_id == known.id
    assert discovered.capabilities["toolhead_count"] == 4
    assert 7125 in checked_ports
    assert 80 in checked_ports


def test_confirm_discovered_printer_returns_known_match_instead_of_duplicate():
    known = Printer(
        id=7,
        name="Bambu A1",
        host="192.168.1.20",
        port=80,
        protocol="http",
        printer_type="mdns:bambu",
        state="confirmed",
        identity_key="mdns:_bambu._tcp.local.:bambu-a1._bambu._tcp.local.",
    )
    source = NetworkScanResult(
        id=4,
        scan_run_id=1,
        name="Bambu A1",
        host="192.168.1.25",
        port=80,
        protocol="http",
        service_type="mdns:bambu",
        identity_key=known.identity_key,
        matched_printer_id=known.id,
        confidence=88,
        evidence=["mDNS service _bambu._tcp.local. advertised Bambu-A1._bambu._tcp.local."],
    )
    session = FakeSession(known_printer=known, scan_results={source.id: source})

    returned = PrinterStore(session).confirm_discovered_printer(
        name="Bambu A1",
        host="192.168.1.25",
        port=80,
        protocol="http",
        service_type="mdns:bambu",
        scan_result_id=source.id,
    )

    assert returned is known
    assert known.host == "192.168.1.25"
    assert known.state == "confirmed"
    assert session.committed is True
    assert not any(isinstance(item, Printer) for item in session.added)


def test_scan_result_updates_known_printer_by_identity_after_ip_change():
    known = Printer(
        id=8,
        name="Bambu A1",
        host="192.168.1.20",
        port=8883,
        protocol="mqtts",
        printer_type="mqtt_probe:bambu_mqtt",
        state="confirmed",
        identity_key="mdns:_bambu._tcp.local.:bambu-a1._bambu._tcp.local.",
    )
    result = PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=100,
            discovered_count=1,
            method="mdns",
            scanned_host_count=0,
            probe_count=4,
        ),
        printers=(
            DiscoveredPrinter(
                name="Bambu A1",
                host="192.168.1.44",
                port=80,
                protocol="http",
                service_type="mdns:bambu",
                confidence=88,
                evidence=("mDNS service _bambu._tcp.local. advertised Bambu-A1._bambu._tcp.local.",),
            ),
        ),
    )
    session = FakeSession(known_printer=known)

    PrinterStore(session).save_scan_result(result)

    saved_result = next(item for item in session.added if isinstance(item, NetworkScanResult))
    assert known.host == "192.168.1.44"
    assert known.port == 8883
    assert known.protocol == "mqtts"
    assert known.state == "online"
    assert saved_result.identity_key == known.identity_key
    assert saved_result.matched_printer_id == known.id


def test_moonraker_identity_key_prefers_stable_device_metadata():
    identity_key = moonraker_identity_key(
        {
            "result": {
                "software_version": "moonraker",
                "hostname": "localhost",
                "machine_id": "SNAP-U1-00A1",
            }
        },
        "snapmaker_moonraker",
    )

    assert identity_key == "moonraker:snapmaker_moonraker:machine_id:snap-u1-00a1"


def test_moonraker_identity_key_uses_hostname_when_device_id_is_missing():
    identity_key = moonraker_identity_key(
        {"result": {"software_version": "moonraker", "hostname": "Snapmaker-U1-A1B2"}},
        "snapmaker_moonraker",
    )

    assert identity_key == "moonraker:snapmaker_moonraker:hostname:snapmaker-u1-a1b2"


def test_moonraker_identity_key_rejects_unstable_hostname():
    identity_key = moonraker_identity_key(
        {"result": {"software_version": "moonraker", "hostname": "localhost"}},
        "moonraker",
    )

    assert identity_key is None


def test_http_probe_detects_octoprint_and_moonraker_markers():
    import httpx

    octoprint_response = httpx.Response(200, text='{"server":"1.9.0","text":"OctoPrint"}')
    octoprint_compat_response = httpx.Response(200, text='{"server":"1.5.0","text":"OctoPrint (Moonraker 1.0.0)"}')
    moonraker_response = httpx.Response(200, text='{"result":{"software_version":"moonraker","klippy_state":"ready"}}')

    octoprint = _detect_octoprint_or_prusalink("192.168.1.20", 80, "http", octoprint_response)
    moonraker_compat = _detect_octoprint_or_prusalink("192.168.1.44", 80, "http", octoprint_compat_response)
    moonraker = _detect_moonraker("192.168.1.21", 7125, "http", moonraker_response)

    assert octoprint is not None
    assert octoprint.service_type == "http_probe:octoprint"
    assert moonraker_compat is not None
    assert moonraker_compat.service_type == "http_probe:moonraker"
    assert moonraker is not None
    assert moonraker.service_type == "http_probe:moonraker"


def test_http_probe_detects_creality_and_snapmaker_markers():
    import httpx

    creality_response = httpx.Response(200, text="<title>Fluidd - Creality K2 Pro</title>")
    snapmaker_response = httpx.Response(200, text='{"brand":"Snapmaker","model":"U1"}')
    bambu_response = httpx.Response(200, text="<title>Bambu Lab A1</title>")

    creality = _detect_generic_http("192.168.1.51", 4408, "http", creality_response)
    snapmaker = _detect_generic_http("192.168.1.52", 8080, "http", snapmaker_response)
    bambu = _detect_generic_http("192.168.1.76", 80, "http", bambu_response)

    assert creality is not None
    assert creality.name == "Creality K2 Pro at 192.168.1.51:4408"
    assert creality.service_type == "http_probe:creality"
    assert snapmaker is not None
    assert snapmaker.name == "Snapmaker U1 at 192.168.1.52:8080"
    assert snapmaker.service_type == "http_probe:snapmaker"
    assert bambu is not None
    assert bambu.name == "Bambu Lab A1 at 192.168.1.76:80"
    assert bambu.service_type == "http_probe:bambu"


def test_moonraker_probe_detects_creality_k2_pro_marker():
    import httpx

    response = httpx.Response(200, text='{"result":{"software_version":"moonraker","model":"Creality K2 Pro"}}')

    printer = _detect_moonraker("192.168.1.185", 7125, "http", response)

    assert printer is not None
    assert printer.name == "Creality K2 Pro Moonraker at 192.168.1.185:7125"
    assert printer.service_type == "http_probe:creality_moonraker"


def test_http_probe_prefers_specific_moonraker_model_after_generic_info(monkeypatch):
    import httpx

    class FakeClient:
        def __init__(self, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def get(self, url):
            if url.endswith("/server/info"):
                return httpx.Response(200, text='{"result":{"software_version":"moonraker","klippy_state":"ready"}}')
            if url.endswith("/printer/info"):
                return httpx.Response(200, text='{"result":{"hostname":"K2Plus-6976","klipper_path":"/usr/share/klipper"}}')
            return httpx.Response(404, text="not found")

    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda host, port, timeout: True)
    monkeypatch.setattr("backend.domains.printers.service.httpx.Client", FakeClient)

    printer = _probe_http_port("192.168.1.185", 7125, 0.1)

    assert printer is not None
    assert printer.name == "Creality K2 Plus Moonraker at 192.168.1.185:7125"
    assert printer.service_type == "http_probe:creality_moonraker"
    assert printer.identity_key == "moonraker:creality_moonraker:hostname:k2plus-6976"


def test_scan_result_updates_known_moonraker_printer_by_identity_after_ip_change():
    identity_key = "moonraker:snapmaker_moonraker:hostname:snapmaker-u1-a1b2"
    known = Printer(
        id=9,
        name="Snapmaker U1",
        host="192.168.1.52",
        port=7125,
        protocol="http",
        printer_type="http_probe:snapmaker_moonraker",
        state="confirmed",
        identity_key=identity_key,
    )
    result = PrinterScanResult(
        summary=PrinterScanSummary(
            status=PrinterScanStatus.COMPLETED,
            duration_ms=100,
            discovered_count=1,
            method="http_probe",
            scanned_host_count=12,
            probe_count=120,
        ),
        printers=(
            DiscoveredPrinter(
                name="Snapmaker U1 Moonraker at 192.168.1.80:7125",
                host="192.168.1.80",
                port=7125,
                protocol="http",
                service_type="http_probe:snapmaker_moonraker",
                confidence=94,
                identity_key=identity_key,
                evidence=("Read-only HTTP probe matched http_probe:snapmaker_moonraker",),
            ),
        ),
    )
    session = FakeSession(known_printer=known)

    PrinterStore(session).save_scan_result(result)

    saved_result = next(item for item in session.added if isinstance(item, NetworkScanResult))
    assert known.host == "192.168.1.80"
    assert known.port == 7125
    assert known.protocol == "http"
    assert known.state == "online"
    assert saved_result.identity_key == identity_key
    assert saved_result.matched_printer_id == known.id


def test_http_probe_does_not_treat_bare_k2_as_creality():
    import httpx

    qnap_like_response = httpx.Response(200, text='<div data-v-8a0ce18a class="content k2-widget">QNAP</div>')

    assert _detect_generic_http("192.168.1.5", 443, "https", qnap_like_response) is None


def test_http_probe_does_not_treat_file_browser_html_as_printer():
    import httpx

    file_browser_response = httpx.Response(
        200,
        text='<title>PiNAS</title><meta name="apple-mobile-web-app-title" content="File Browser" />'
        '<script>window.FileBrowser = {"Name":"PiNAS","Version":"2.63.14"}</script>',
    )

    assert _detect_generic_http("192.168.1.6", 8080, "http", file_browser_response) is None


def test_tcp_only_support_ports_are_not_printer_proof(monkeypatch):
    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda host, port, timeout: True)

    assert _probe_http_port("192.168.1.76", 6000, 0.1) is None


def test_mqtt_probe_labels_confirmed_bambu_mqtt_port(monkeypatch):
    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda host, port, timeout: True)
    monkeypatch.setattr("backend.domains.printers.service._probe_mqtt_over_tls", lambda host, port, timeout: "mqtt")

    printer = _probe_http_port("192.168.1.53", 8883, 0.1)

    assert printer is not None
    assert printer.protocol == "mqtts"
    assert printer.service_type == "mqtt_probe:bambu_mqtt"
    assert printer.confidence == 90
    assert "MQTT over TLS CONNACK" in printer.evidence[0]


def test_bambu_mqtt_capabilities_explain_lan_onboarding_tradeoffs():
    endpoint = DiscoveredPrinter(
        name="Bambu Lab MQTT broker at 192.168.1.53:8883",
        host="192.168.1.53",
        port=8883,
        protocol="mqtts",
        service_type="mqtt_probe:bambu_mqtt",
        confidence=90,
        evidence=("MQTT over TLS CONNACK received; no publish/control commands sent",),
    )

    capabilities = _endpoint_capabilities(endpoint)

    assert "Bambu LAN MQTT" in capabilities
    assert "Scan-only discovery without access code" in capabilities
    assert "Full telemetry requires LAN access code" in capabilities
    assert "LAN/Developer mode may limit Bambu Handy or cloud workflows" in capabilities


def test_http_probe_uses_tls_verification_for_https(monkeypatch):
    client_kwargs = {}

    class FakeClient:
        def __init__(self, **kwargs):
            client_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def get(self, url):
            import httpx

            return httpx.Response(404, text="not a printer")

    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda host, port, timeout: True)
    monkeypatch.setattr("backend.domains.printers.service.httpx.Client", FakeClient)

    assert _probe_http_port("192.168.1.77", 443, 0.1) is None
    assert client_kwargs["verify"] is True


def test_http_scan_keeps_partial_results_when_one_worker_fails(monkeypatch):
    def fake_probe(host, port, timeout):
        if host == "192.168.50.2":
            raise RuntimeError("probe failed")
        return (
            DiscoveredPrinter(
                name=f"Printer {host}",
                host=host,
                port=80,
                protocol="http",
                service_type="http_probe:moonraker",
                confidence=90,
            )
        )

    monkeypatch.setattr("backend.domains.printers.service._limited_hosts", lambda network, max_hosts: ("192.168.50.1", "192.168.50.2"))
    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda host, port, timeout: True)
    monkeypatch.setattr("backend.domains.printers.service._probe_http_port", fake_probe)

    result = _scan_http_printers("192.168.50.0/24", max_hosts=2, ports=(80,), connect_timeout_seconds=0.1)

    assert result.summary.status == PrinterScanStatus.COMPLETED
    assert result.summary.discovered_count == 1
    assert result.printers[0].host == "192.168.50.1"


def test_http_scan_deadline_returns_partial_results_from_completed_hosts(monkeypatch):
    def fake_probe(host, port, timeout):
        if host == "192.168.50.2":
            sleep(1.0)
            return None
        return (
            DiscoveredPrinter(
                name=f"Printer {host}",
                host=host,
                port=80,
                protocol="http",
                service_type="http_probe:moonraker",
                confidence=90,
            )
        )

    monkeypatch.setattr("backend.domains.printers.service._limited_hosts", lambda network, max_hosts: ("192.168.50.1", "192.168.50.2"))
    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda host, port, timeout: True)
    monkeypatch.setattr("backend.domains.printers.service._probe_http_port", fake_probe)

    started = monotonic()
    result = _scan_http_printers(
        "192.168.50.0/24",
        max_hosts=2,
        ports=(80,),
        connect_timeout_seconds=0.1,
        scan_timeout_seconds=0.2,
    )
    elapsed = monotonic() - started

    assert elapsed < 0.7
    assert result.summary.status == PrinterScanStatus.COMPLETED
    assert result.summary.discovered_count == 1
    assert result.printers[0].host == "192.168.50.1"


def test_http_scan_schedules_prioritized_ports_across_hosts(monkeypatch):
    seen = []

    def fake_probe(host, port, timeout):
        seen.append((host, port))
        if host == "192.168.50.185" and port == 4408:
            return DiscoveredPrinter(
                name="Klipper/Moonraker at 192.168.50.185:4408",
                host=host,
                port=port,
                protocol="http",
                service_type="http_probe:moonraker",
                confidence=84,
            )
        return None

    hosts = ("192.168.50.1", "192.168.50.44", "192.168.50.185")
    monkeypatch.setattr("backend.domains.printers.service._limited_hosts", lambda network, max_hosts: hosts)
    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda host, port, timeout: True)
    monkeypatch.setattr("backend.domains.printers.service._probe_http_port", fake_probe)

    result = _scan_http_printers(
        "192.168.50.0/24",
        max_hosts=254,
        ports=(80, 443, 4408, 7125),
        connect_timeout_seconds=0.1,
        scan_timeout_seconds=1.0,
    )

    assert _prioritized_probe_ports((80, 443, 4408, 7125)) == (7125, 4408, 80, 443)
    assert _prioritized_probe_ports((80, 8883, 7125, 4408)) == (7125, 8883, 4408, 80)
    seen_by_host = {host: [port for seen_host, port in seen if seen_host == host] for host in hosts}
    assert seen_by_host == {host: [7125, 4408, 80, 443] for host in hosts}
    assert result.summary.discovered_count == 1
    assert result.printers[0].host == "192.168.50.185"


def test_mdns_metadata_filters_paper_and_generic_http_services():
    assert _mdns_printer_metadata("_ipp._tcp.local.", "HP OfficeJet Pro 8720") is None
    assert _mdns_printer_metadata("_http._tcp.local.", "RomoCloud") is None
    assert _mdns_printer_metadata("_http._tcp.local.", "Bambu Lab X1") == ("http", "mdns:bambu", 86)
    assert _mdns_printer_metadata("_bambulab._tcp.local.", "Bambu Lab A1") == ("http", "mdns:bambu", 88)
    assert _mdns_printer_metadata("_bambulab._tcp.local.", "Bambu Lab H2") == ("http", "mdns:bambu", 88)
    assert _mdns_printer_metadata("_creality._tcp.local.", "Creality K2 Pro") == ("http", "mdns:creality", 84)
    assert _mdns_printer_metadata("_http._tcp.local.", "K2 storage widget") is None
    assert _mdns_printer_metadata("_http._tcp.local.", "U1 storage widget") is None
    assert _mdns_printer_metadata("_snapmaker._tcp.local.", "Snapmaker U1") == ("http", "mdns:snapmaker", 82)
    assert _mdns_printer_metadata("_snapmaker._tcp.local.", "U1") == ("http", "mdns:snapmaker", 82)
    assert _mdns_printer_metadata("_moonraker._tcp.local.", "mainsail") == ("http", "_moonraker._tcp.local.", 90)


def test_combined_scan_passes_timeout_budget_to_http_probe(monkeypatch):
    captured = {}

    def fake_mdns(timeout_seconds):
        return PrinterScanResult(
            summary=PrinterScanSummary(
                status=PrinterScanStatus.COMPLETED,
                duration_ms=1,
                discovered_count=0,
                method="mdns",
                probe_count=0,
            ),
            printers=(),
        )

    def fake_http(target_cidr, max_hosts, ports, connect_timeout_seconds, scan_timeout_seconds=None):
        captured["scan_timeout_seconds"] = scan_timeout_seconds
        return PrinterScanResult(
            summary=PrinterScanSummary(
                status=PrinterScanStatus.COMPLETED,
                duration_ms=1,
                discovered_count=0,
                method="http_probe",
                scanned_host_count=0,
                probe_count=0,
            ),
            printers=(),
        )

    monkeypatch.setattr("backend.domains.printers.service._scan_mdns", fake_mdns)
    monkeypatch.setattr("backend.domains.printers.service._scan_http_printers", fake_http)

    scan_lan_for_printers(timeout_seconds=4.5, scan_method="combined")

    assert captured["scan_timeout_seconds"] == 4.5


def test_octoprint_and_moonraker_status_parsers_are_read_only():
    octoprint = parse_octoprint_status(
        {"server": "1.10.0", "api": "0.1"},
        {"state": {"text": "Operational"}},
    )
    moonraker = parse_moonraker_status(
        {"result": {"software_version": "v0.9", "klippy_state": "ready", "components": ["klippy_apis"]}},
        {"result": {"state": "ready"}},
    )

    assert octoprint.adapter_type == "octoprint"
    assert octoprint.state == "operational"
    assert octoprint.capabilities["control_enabled"] is False
    assert moonraker.adapter_type == "moonraker"
    assert moonraker.state == "ready"
    assert moonraker.capabilities["read_only_status"] is True


def test_moonraker_capability_parser_extracts_build_volume_and_multi_head_fields():
    payload = {
        "result": {
            "status": {
                "toolhead": {"axis_maximum": [320.0, 320.0, 320.0, 0]},
                "configfile": {
                    "settings": {
                        "extruder": {"max_temp": 300, "nozzle_diameter": 0.4},
                        "extruder1": {"max_temp": 300, "nozzle_diameter": 0.4},
                        "extruder2": {"max_temp": 300, "nozzle_diameter": 0.4},
                        "extruder3": {"max_temp": 300, "nozzle_diameter": 0.4},
                        "heater_bed": {"max_temp": 110},
                    }
                },
            }
        }
    }

    capabilities = _moonraker_capabilities_from_objects(payload, "http_probe:snapmaker_moonraker")

    assert capabilities["build_volume_mm"] == {"x": 320, "y": 320, "z": 320}
    assert capabilities["toolhead_count"] == 4
    assert capabilities["color_count"] == 4
    assert capabilities["multi_head"] is True
    assert capabilities["multi_color"] is True
    assert capabilities["max_nozzle_temp_c"] == 300
    assert capabilities["max_bed_temp_c"] == 110


def test_moonraker_adapter_maps_file_and_job_requests(monkeypatch):
    requests = []

    class FakeClient:
        def __init__(self, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def get(self, url, params=None):
            requests.append(("GET", url, params))
            return FakeResponse(
                [
                    {"path": "cube.gcode", "size": 100, "modified": 1.0, "permissions": "rw"},
                ]
            )

        def post(self, url, files=None, data=None):
            requests.append(("POST", url, files, data))
            return FakeResponse("ok")

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    monkeypatch.setattr("backend.domains.printers.adapters.httpx.Client", FakeClient)
    printer = FakeMoonrakerPrinter()

    files = list_moonraker_files(printer)
    upload = upload_moonraker_file(printer, "new.gcode.gz", b"G1 X1")
    start = start_moonraker_print(printer, "cube.gcode")
    pause = pause_moonraker_print(printer)
    resume = resume_moonraker_print(printer)
    cancel = cancel_moonraker_print(printer)

    assert files[0].path == "cube.gcode"
    assert upload.action == "upload"
    assert start.action == "start"
    assert pause.action == "pause"
    assert resume.action == "resume"
    assert cancel.action == "cancel"
    assert ("GET", "http://192.168.1.80:7125/server/files/list", {"root": "gcodes"}) in requests
    assert any(request[1].endswith("/printer/print/start?filename=cube.gcode") for request in requests)
    assert any(request[1].endswith("/printer/print/pause") for request in requests)
    assert any(request[1].endswith("/printer/print/resume") for request in requests)
    assert any(request[1].endswith("/printer/print/cancel") for request in requests)


def test_moonraker_upload_rejects_non_sliced_files():
    with pytest.raises(InvalidPrintFileError):
        upload_moonraker_file(FakeMoonrakerPrinter(), "model.stl", b"solid cube")


def test_mqtt_probe_ignores_unacknowledged_bambu_mqtt_port(monkeypatch):
    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda host, port, timeout: True)
    monkeypatch.setattr("backend.domains.printers.service._probe_mqtt_over_tls", lambda host, port, timeout: "tcp")

    printer = _probe_http_port("192.168.1.53", 8883, 0.1)

    assert printer is None


def test_http_probe_host_limits_are_enforced():
    network = _resolve_probe_network("192.168.50.0/24")

    hosts = _limited_hosts(network, max_hosts=3)

    assert hosts == ("192.168.50.1", "192.168.50.2", "192.168.50.3")
