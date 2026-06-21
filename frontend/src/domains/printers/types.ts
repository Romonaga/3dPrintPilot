export type Printer = {
  id: number;
  name: string;
  host: string;
  port: number;
  protocol: string;
  printerType: string;
  state: string;
  identityKey: string | null;
  adapterType: string | null;
  capabilities: Record<string, unknown>;
  credentialConfigured: boolean;
  lastStatus: Record<string, unknown>;
  lastStatusAt: string | null;
  buildVolumeXmm: number | null;
  buildVolumeYmm: number | null;
  buildVolumeZmm: number | null;
};

export type PrinterJobStatus = {
  printerId: number;
  state: string;
  filename: string | null;
  progress: number | null;
  message: string | null;
  rawStatus: Record<string, unknown>;
  observedAt: string;
};

export type PrinterFile = {
  path: string;
  size: number | null;
  modified: number | null;
  permissions: string | null;
};

export type PrinterActionResult = {
  printerId: number;
  action: string;
  accepted: boolean;
  rawResponse: unknown;
};

export type DiscoveredPrinter = {
  name: string;
  host: string;
  port: number;
  protocol: string;
  serviceType: string;
  confidence: number;
  state: string;
  evidence: string[];
  scanResultId: number | null;
  identityKey: string | null;
  matchedPrinterId: number | null;
};

export type PrinterEndpointGroup = {
  host: string;
  name: string;
  inferredType: string;
  identityKey: string | null;
  matchedPrinterId: number | null;
  confidence: number;
  ports: number[];
  capabilities: string[];
  endpoints: DiscoveredPrinter[];
};

export type PrinterScanResult = {
  summary: {
    scanRunId: number | null;
    status: string;
    durationMs: number;
    discoveredCount: number;
    method: string;
    scannedHostCount: number;
    probeCount: number;
  };
  printers: DiscoveredPrinter[];
  groups: PrinterEndpointGroup[];
};

export type PrinterScanSettings = {
  scanMethod: "combined" | "mdns" | "http_probe";
  targetCidr: string;
  maxHosts: number;
  timeoutSeconds: number;
  connectTimeoutSeconds: number;
  ports: string;
};

export type CreatePrinterInput = {
  name: string;
  host: string;
  port: number;
  protocol: string;
  printerType: string;
  buildVolumeXmm: number | null;
  buildVolumeYmm: number | null;
  buildVolumeZmm: number | null;
};
