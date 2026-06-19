import {
  type CreatePrinterInput,
  type DiscoveredPrinter,
  type Printer,
  type PrinterScanResult,
  type PrinterScanSettings
} from "../types";
import { apiFetch } from "../../../lib/apiFetch";

type ApiPrinter = {
  id: number;
  name: string;
  host: string;
  port: number;
  protocol: string;
  printer_type: string;
  state: string;
  adapter_type: string | null;
  capabilities: Record<string, unknown>;
  credential_configured: boolean;
  last_status: Record<string, unknown>;
  last_status_at: string | null;
  build_volume_x_mm: number | null;
  build_volume_y_mm: number | null;
  build_volume_z_mm: number | null;
};

type ApiDiscoveredPrinter = {
  name: string;
  host: string;
  port: number;
  protocol: string;
  service_type: string;
  confidence: number;
  state: string;
  evidence?: string[];
  scan_result_id?: number | null;
};

type ApiPrinterScan = {
  summary: {
    scan_run_id: number | null;
    status: string;
    duration_ms: number;
    discovered_count: number;
    method: string;
    scanned_host_count: number;
    probe_count: number;
  };
  printers: ApiDiscoveredPrinter[];
  groups?: Array<{
    host: string;
    name: string;
    inferred_type: string;
    confidence: number;
    ports: number[];
    capabilities: string[];
    endpoints: ApiDiscoveredPrinter[];
  }>;
};

export async function listPrinters(): Promise<Printer[]> {
  const response = await apiFetch("/api/printers");
  if (!response.ok) {
    throw new Error(`Printer list failed with HTTP ${response.status}`);
  }
  const printers = (await response.json()) as ApiPrinter[];
  return printers.map(fromApiPrinter);
}

export async function createPrinter(input: CreatePrinterInput): Promise<Printer> {
  const response = await apiFetch("/api/printers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: input.name,
      host: input.host,
      port: input.port,
      protocol: input.protocol,
      printer_type: input.printerType,
      build_volume_x_mm: input.buildVolumeXmm,
      build_volume_y_mm: input.buildVolumeYmm,
      build_volume_z_mm: input.buildVolumeZmm
    })
  });
  if (!response.ok) {
    throw new Error(`Add printer failed with HTTP ${response.status}`);
  }
  return fromApiPrinter(await response.json());
}

export async function confirmDiscoveredPrinter(input: DiscoveredPrinter): Promise<Printer> {
  const response = await apiFetch("/api/printers/confirm-discovered", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: input.name,
      host: input.host,
      port: input.port,
      protocol: input.protocol,
      service_type: input.serviceType,
      confidence: input.confidence,
      scan_result_id: input.scanResultId
    })
  });
  if (!response.ok) {
    throw new Error(`Confirm printer failed with HTTP ${response.status}`);
  }
  return fromApiPrinter(await response.json());
}

export async function deletePrinter(printerId: number): Promise<void> {
  const response = await apiFetch(`/api/printers/${printerId}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`Delete printer failed with HTTP ${response.status}`);
  }
}

export function fromDiscoveredPrinter(printer: DiscoveredPrinter): CreatePrinterInput {
  return {
    name: printer.name,
    host: printer.host,
    port: printer.port,
    protocol: printer.protocol,
    printerType: printer.serviceType.replace("http_probe:", "").replace(/^_/, "").split(".")[0] || "unknown",
    buildVolumeXmm: null,
    buildVolumeYmm: null,
    buildVolumeZmm: null
  };
}

export async function scanPrinters(settings: PrinterScanSettings): Promise<PrinterScanResult> {
  const response = await apiFetch("/api/printers/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      timeout_seconds: settings.timeoutSeconds,
      scan_method: settings.scanMethod,
      target_cidr: settings.targetCidr.trim() || null,
      max_hosts: settings.maxHosts,
      connect_timeout_seconds: settings.connectTimeoutSeconds,
      ports: settings.ports
        .split(",")
        .map((port) => Number(port.trim()))
        .filter((port) => Number.isInteger(port) && port > 0 && port <= 65535)
    })
  });
  if (!response.ok) {
    throw new Error(`Printer scan failed with HTTP ${response.status}`);
  }
  const scan = (await response.json()) as ApiPrinterScan;
  return {
    summary: {
      scanRunId: scan.summary.scan_run_id,
      status: scan.summary.status,
      durationMs: scan.summary.duration_ms,
      discoveredCount: scan.summary.discovered_count,
      method: scan.summary.method,
      scannedHostCount: scan.summary.scanned_host_count,
      probeCount: scan.summary.probe_count
    },
    printers: scan.printers.map((printer) => ({
      name: printer.name,
      host: printer.host,
      port: printer.port,
      protocol: printer.protocol,
      serviceType: printer.service_type,
      confidence: printer.confidence,
      state: printer.state,
      evidence: printer.evidence ?? [],
      scanResultId: printer.scan_result_id ?? null
    })),
    groups: (scan.groups ?? []).map((group) => ({
      host: group.host,
      name: group.name,
      inferredType: group.inferred_type,
      confidence: group.confidence,
      ports: group.ports,
      capabilities: group.capabilities,
      endpoints: group.endpoints.map((endpoint) => ({
        name: endpoint.name,
        host: endpoint.host,
        port: endpoint.port,
        protocol: endpoint.protocol,
          serviceType: endpoint.service_type,
          confidence: endpoint.confidence,
          state: endpoint.state,
          evidence: endpoint.evidence ?? [],
          scanResultId: endpoint.scan_result_id ?? null
        }))
    }))
  };
}

function fromApiPrinter(printer: ApiPrinter): Printer {
  return {
    id: printer.id,
    name: printer.name,
    host: printer.host,
    port: printer.port,
    protocol: printer.protocol,
    printerType: printer.printer_type,
    state: printer.state,
    adapterType: printer.adapter_type,
    capabilities: printer.capabilities,
    credentialConfigured: printer.credential_configured,
    lastStatus: printer.last_status,
    lastStatusAt: printer.last_status_at,
    buildVolumeXmm: printer.build_volume_x_mm,
    buildVolumeYmm: printer.build_volume_y_mm,
    buildVolumeZmm: printer.build_volume_z_mm
  };
}
