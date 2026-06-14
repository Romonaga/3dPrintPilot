export type CompatibilityItem = {
  code: string;
  severity: "pass" | "warning" | "fail";
  message: string;
};

export type CompatibilityCheckResult = {
  id: number;
  scanResultId: number;
  printerId: number;
  status: "pass" | "warning" | "fail";
  sourceType: string;
  confidenceLabel: string;
  modelTitle: string;
  modelUrl: string;
  printerName: string;
  durationMs: number;
  createdAt: string;
  items: CompatibilityItem[];
};

export type CompatibilityRunResult = {
  scanRunId: number;
  printerCount: number;
  candidateCount: number;
  checkCount: number;
  checks: CompatibilityCheckResult[];
};
