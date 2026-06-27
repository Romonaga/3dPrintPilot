import {
  type Printer,
  type PrinterActionResult,
  type PrinterCapabilityDiagnostics,
  type PrinterEngine,
  type PrinterFile,
  type PrinterJobStatus,
  type PrinterStatus
} from "../types";
import {
  type ApiPrinter,
  type ApiPrinterActionResult,
  type ApiPrinterCapabilityDiagnostics,
  type ApiPrinterEngine,
  type ApiPrinterFile,
  type ApiPrinterJobStatus,
  type ApiPrinterStatus,
  type ApiPrinterTemperature
} from "./printerApiTypes";

export function fromApiPrinter(printer: ApiPrinter): Printer {
  return {
    id: printer.id,
    name: printer.name,
    host: printer.host,
    port: printer.port,
    protocol: printer.protocol,
    printerType: printer.printer_type,
    state: printer.state,
    identityKey: printer.identity_key ?? null,
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

export function fromApiPrinterJobStatus(status: ApiPrinterJobStatus): PrinterJobStatus {
  return {
    printerId: status.printer_id,
    state: status.state,
    filename: status.filename,
    progress: status.progress,
    message: status.message,
    bedTemperature: status.bed_temperature ? fromApiPrinterTemperature(status.bed_temperature) : null,
    toolheads: (status.toolheads ?? []).map((toolhead) => ({
      name: toolhead.name,
      label: toolhead.label,
      index: toolhead.index,
      currentTemperature: toolhead.current_temperature ? fromApiPrinterTemperature(toolhead.current_temperature) : null,
      color: toolhead.color,
      colorSource: toolhead.color_source ?? null,
      material: toolhead.material ?? null,
      materialSource: toolhead.material_source ?? null,
      vendor: toolhead.vendor ?? null,
      subtype: toolhead.subtype ?? null
    })),
    rawStatus: status.raw_status,
    observedAt: status.observed_at
  };
}

export function fromApiPrinterStatus(status: ApiPrinterStatus): PrinterStatus {
  return {
    printerId: status.printer_id,
    adapterType: status.adapter_type,
    state: status.state,
    capabilities: status.capabilities,
    rawStatus: status.raw_status,
    observedAt: status.observed_at
  };
}

export function fromApiPrinterCapabilityDiagnostics(diagnostics: ApiPrinterCapabilityDiagnostics): PrinterCapabilityDiagnostics {
  return {
    printerId: diagnostics.printer_id,
    adapterType: diagnostics.adapter_type,
    extensionAgentsAvailable: diagnostics.extension_agents_available,
    extensionAgents: diagnostics.extension_agents ?? [],
    spoolmanAvailable: diagnostics.spoolman_available,
    spoolmanStatus: diagnostics.spoolman_status ?? null,
    probeErrors: diagnostics.probe_errors ?? {},
    observedAt: diagnostics.observed_at
  };
}

export function fromApiPrinterEngine(engine: ApiPrinterEngine): PrinterEngine {
  return {
    engineId: engine.engine_id,
    displayName: engine.display_name,
    description: engine.description,
    capabilities: engine.capabilities
  };
}

function fromApiPrinterTemperature(temperature: ApiPrinterTemperature) {
  return {
    currentC: temperature.current_c,
    targetC: temperature.target_c,
    power: temperature.power
  };
}

export function fromApiPrinterFile(file: ApiPrinterFile): PrinterFile {
  return {
    path: file.path,
    size: file.size,
    modified: file.modified,
    permissions: file.permissions
  };
}

export function fromApiPrinterActionResult(result: ApiPrinterActionResult): PrinterActionResult {
  return {
    printerId: result.printer_id,
    action: result.action,
    accepted: result.accepted,
    rawResponse: result.raw_response
  };
}
