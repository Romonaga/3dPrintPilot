import {
  type CreatePrinterInput,
  type DiscoveredPrinter,
  type Printer,
  type PrinterActionResult,
  type PrinterCapabilityDiagnostics,
  type PrinterEngine,
  type PrinterFile,
  type PrinterJobStatus,
  type PrinterScanResult,
  type PrinterScanSettings,
  type PrinterStatus
} from "../types";
import { apiFetch } from "../../../lib/apiFetch";
import {
  fromApiPrinter,
  fromApiPrinterActionResult,
  fromApiPrinterCapabilityDiagnostics,
  fromApiPrinterEngine,
  fromApiPrinterFile,
  fromApiPrinterJobStatus,
  fromApiPrinterStatus
} from "./printerApiMappers";
import { type ApiPrinter, type ApiPrinterEngine, type ApiPrinterFile, type ApiPrinterScan } from "./printerApiTypes";

export async function listPrinters(): Promise<Printer[]> {
  const response = await apiFetch("/api/printers");
  if (!response.ok) {
    throw new Error(`Printer list failed with HTTP ${response.status}`);
  }
  const printers = (await response.json()) as ApiPrinter[];
  return printers.map(fromApiPrinter);
}

export async function getPrinterJobStatus(printerId: number): Promise<PrinterJobStatus> {
  const response = await apiFetch(`/api/printers/${printerId}/job-status`);
  if (!response.ok) {
    throw new Error(`Printer job status failed with HTTP ${response.status}`);
  }
  return fromApiPrinterJobStatus(await response.json());
}

export async function getPrinterStatus(printerId: number): Promise<PrinterStatus> {
  const response = await apiFetch(`/api/printers/${printerId}/status`);
  if (!response.ok) {
    throw new Error(`Printer status failed with HTTP ${response.status}`);
  }
  return fromApiPrinterStatus(await response.json());
}

export async function getPrinterCapabilityDiagnostics(printerId: number): Promise<PrinterCapabilityDiagnostics> {
  const response = await apiFetch(`/api/printers/${printerId}/capability-diagnostics`);
  if (!response.ok) {
    throw new Error(`Printer capability diagnostics failed with HTTP ${response.status}`);
  }
  return fromApiPrinterCapabilityDiagnostics(await response.json());
}

export async function listPrinterEngines(): Promise<PrinterEngine[]> {
  const response = await apiFetch("/api/printers/engines");
  if (!response.ok) {
    throw new Error(`Printer engine list failed with HTTP ${response.status}`);
  }
  const engines = (await response.json()) as ApiPrinterEngine[];
  return engines.map(fromApiPrinterEngine);
}

export async function refreshPrinterEngines(): Promise<PrinterEngine[]> {
  const response = await apiFetch("/api/printers/engines/refresh", { method: "POST" });
  if (!response.ok) {
    throw new Error(`Printer engine refresh failed with HTTP ${response.status}`);
  }
  const engines = (await response.json()) as ApiPrinterEngine[];
  return engines.map(fromApiPrinterEngine);
}

export async function listPrinterFiles(printerId: number): Promise<PrinterFile[]> {
  const response = await apiFetch(`/api/printers/${printerId}/files`);
  if (!response.ok) {
    throw new Error(`Printer file list failed with HTTP ${response.status}`);
  }
  const files = (await response.json()) as ApiPrinterFile[];
  return files.map(fromApiPrinterFile);
}

export async function uploadPrinterFile(printerId: number, file: File): Promise<PrinterActionResult> {
  const body = new FormData();
  body.append("file", file);
  const response = await apiFetch(`/api/printers/${printerId}/files`, {
    method: "POST",
    body
  }, { timeoutMs: 180_000 });
  if (!response.ok) {
    throw new Error(`Printer file upload failed with HTTP ${response.status}`);
  }
  return fromApiPrinterActionResult(await response.json());
}

export async function startPrinterFile(printerId: number, filename: string): Promise<PrinterActionResult> {
  const response = await apiFetch(`/api/printers/${printerId}/print/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename })
  });
  if (!response.ok) {
    throw new Error(`Printer start failed with HTTP ${response.status}`);
  }
  return fromApiPrinterActionResult(await response.json());
}

export async function pausePrinterPrint(printerId: number): Promise<PrinterActionResult> {
  return postPrinterAction(printerId, "pause");
}

export async function resumePrinterPrint(printerId: number): Promise<PrinterActionResult> {
  return postPrinterAction(printerId, "resume");
}

export async function cancelPrinterPrint(printerId: number): Promise<PrinterActionResult> {
  return postPrinterAction(printerId, "cancel");
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
      scan_result_id: input.scanResultId,
      identity_key: input.identityKey,
      capabilities: input.capabilities,
      build_volume_x_mm: input.buildVolumeXmm,
      build_volume_y_mm: input.buildVolumeYmm,
      build_volume_z_mm: input.buildVolumeZmm
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
    buildVolumeXmm: printer.buildVolumeXmm,
    buildVolumeYmm: printer.buildVolumeYmm,
    buildVolumeZmm: printer.buildVolumeZmm
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
  }, { timeoutMs: 180_000 });
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
      scanResultId: printer.scan_result_id ?? null,
      identityKey: printer.identity_key ?? null,
      matchedPrinterId: printer.matched_printer_id ?? null,
      capabilities: printer.capabilities ?? {},
      buildVolumeXmm: printer.build_volume_x_mm ?? null,
      buildVolumeYmm: printer.build_volume_y_mm ?? null,
      buildVolumeZmm: printer.build_volume_z_mm ?? null
    })),
    groups: (scan.groups ?? []).map((group) => ({
      host: group.host,
      name: group.name,
      inferredType: group.inferred_type,
      identityKey: group.identity_key ?? null,
      matchedPrinterId: group.matched_printer_id ?? null,
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
        scanResultId: endpoint.scan_result_id ?? null,
        identityKey: endpoint.identity_key ?? null,
        matchedPrinterId: endpoint.matched_printer_id ?? null,
        capabilities: endpoint.capabilities ?? {},
        buildVolumeXmm: endpoint.build_volume_x_mm ?? null,
        buildVolumeYmm: endpoint.build_volume_y_mm ?? null,
        buildVolumeZmm: endpoint.build_volume_z_mm ?? null
      }))
    }))
  };
}

async function postPrinterAction(printerId: number, action: "pause" | "resume" | "cancel"): Promise<PrinterActionResult> {
  const response = await apiFetch(`/api/printers/${printerId}/print/${action}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Printer ${action} failed with HTTP ${response.status}`);
  }
  return fromApiPrinterActionResult(await response.json());
}
