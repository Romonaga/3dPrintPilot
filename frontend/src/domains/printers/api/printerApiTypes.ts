export type ApiPrinter = {
  id: number;
  name: string;
  host: string;
  port: number;
  protocol: string;
  printer_type: string;
  state: string;
  identity_key: string | null;
  adapter_type: string | null;
  capabilities: Record<string, unknown>;
  credential_configured: boolean;
  last_status: Record<string, unknown>;
  last_status_at: string | null;
  build_volume_x_mm: number | null;
  build_volume_y_mm: number | null;
  build_volume_z_mm: number | null;
};

export type ApiDiscoveredPrinter = {
  name: string;
  host: string;
  port: number;
  protocol: string;
  service_type: string;
  confidence: number;
  state: string;
  evidence?: string[];
  scan_result_id?: number | null;
  identity_key?: string | null;
  matched_printer_id?: number | null;
  capabilities?: Record<string, unknown>;
  build_volume_x_mm?: number | null;
  build_volume_y_mm?: number | null;
  build_volume_z_mm?: number | null;
};

export type ApiPrinterScan = {
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
    identity_key?: string | null;
    matched_printer_id?: number | null;
    confidence: number;
    ports: number[];
    capabilities: string[];
    endpoints: ApiDiscoveredPrinter[];
  }>;
};

export type ApiPrinterJobStatus = {
  printer_id: number;
  state: string;
  filename: string | null;
  progress: number | null;
  message: string | null;
  bed_temperature?: ApiPrinterTemperature | null;
  toolheads?: ApiPrinterToolheadTelemetry[];
  raw_status: Record<string, unknown>;
  observed_at: string;
};

export type ApiPrinterStatus = {
  printer_id: number;
  adapter_type: string;
  state: string;
  capabilities: Record<string, unknown>;
  raw_status: Record<string, unknown>;
  observed_at: string;
};

export type ApiPrinterCapabilityDiagnostics = {
  printer_id: number;
  adapter_type: string;
  extension_agents_available: boolean;
  extension_agents?: Array<Record<string, unknown>>;
  spoolman_available: boolean;
  spoolman_status?: Record<string, unknown> | null;
  probe_errors?: Record<string, string>;
  observed_at: string;
};

export type ApiPrinterTemperature = {
  current_c: number | null;
  target_c: number | null;
  power: number | null;
};

export type ApiPrinterToolheadTelemetry = {
  name: string;
  label: string;
  index: number;
  current_temperature: ApiPrinterTemperature | null;
  color: string | null;
  color_source?: string | null;
  material?: string | null;
  material_source?: string | null;
  vendor?: string | null;
  subtype?: string | null;
};

export type ApiPrinterFile = {
  path: string;
  size: number | null;
  modified: number | null;
  permissions: string | null;
};

export type ApiPrinterActionResult = {
  printer_id: number;
  action: string;
  accepted: boolean;
  raw_response: unknown;
};

export type ApiPrinterEngine = {
  engine_id: string;
  display_name: string;
  description: string;
  capabilities: Record<string, unknown>;
};
