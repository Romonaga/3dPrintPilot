from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.domains.printers.adapters import parse_moonraker_status, parse_octoprint_status
from backend.domains.printers.entities import DiscoveredPrinter, PrinterScanResult, PrinterScanStatus, PrinterScanSummary
from backend.domains.printers.models import NetworkScanResult, NetworkScanRun, Printer
from backend.domains.printers.routes import get_printer_store
from backend.domains.printers.service import (
    _detect_moonraker,
    _detect_generic_http,
    _detect_octoprint_or_prusalink,
    _limited_hosts,
    _probe_http_port,
    _resolve_probe_network,
)
from backend.domains.printers.store import PrinterStore
from backend.db.base import Base


class FakePrinter:
    id = 12
    name = "Manual MK4"
    host = "192.168.1.50"
    port = 80
    protocol = "http"
    printer_type = "prus link"
    state = "manual"
    adapter_type = None
    capabilities = {}
    credential_secret_name = None
    last_status = {}
    last_status_at = None
    build_volume_x_mm = 250
    build_volume_y_mm = 210
    build_volume_z_mm = 220


class FakePrinterStore:
    def list_printers(self):
        return [FakePrinter()]

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
        printer.capabilities = {"read_only_status": printer.adapter_type is not None}
        return printer

    def delete_printer(self, printer_id):
        return printer_id == 12

    def save_scan_result(self, result):
        run = NetworkScanRun()
        run.id = 44
        return run


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

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


def test_printer_models_are_registered():
    table_names = set(Base.metadata.tables)

    assert Printer.__tablename__ in table_names
    assert NetworkScanRun.__tablename__ in table_names
    assert NetworkScanResult.__tablename__ in table_names
    assert "scanned_host_count" in NetworkScanRun.__table__.columns
    assert "probe_count" in NetworkScanRun.__table__.columns


def test_printer_api_lists_and_adds_printers():
    app = create_app()
    app.dependency_overrides[get_printer_store] = lambda: FakePrinterStore()
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

    creality_response = httpx.Response(200, text="<title>Fluidd - Creality K2</title>")
    snapmaker_response = httpx.Response(200, text='{"brand":"Snapmaker","model":"U1"}')

    creality = _detect_generic_http("192.168.1.51", 4408, "http", creality_response)
    snapmaker = _detect_generic_http("192.168.1.52", 8080, "http", snapmaker_response)

    assert creality is not None
    assert creality.service_type == "http_probe:creality"
    assert snapmaker is not None
    assert snapmaker.service_type == "http_probe:snapmaker"


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


def test_mqtt_probe_ignores_unacknowledged_bambu_mqtt_port(monkeypatch):
    monkeypatch.setattr("backend.domains.printers.service._tcp_port_open", lambda host, port, timeout: True)
    monkeypatch.setattr("backend.domains.printers.service._probe_mqtt_over_tls", lambda host, port, timeout: "tcp")

    printer = _probe_http_port("192.168.1.53", 8883, 0.1)

    assert printer is None


def test_http_probe_host_limits_are_enforced():
    network = _resolve_probe_network("192.168.50.0/24")

    hosts = _limited_hosts(network, max_hosts=3)

    assert hosts == ("192.168.50.1", "192.168.50.2", "192.168.50.3")
