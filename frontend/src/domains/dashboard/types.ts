export type PrinterSummary = {
  id: string;
  name: string;
  state: string;
  buildVolume: string;
  confidence: number;
};

export type CompatibilityCheck = {
  id: string;
  model: string;
  printer: string;
  result: string;
  tone: "ok" | "warn" | "bad";
};

export type AiUsageSummary = {
  localModel: string;
  fallbackStatus: string;
  estimatedMonthToDate: string;
  budgetRemaining: string;
  status: string;
};

export type ResourceSnapshot = {
  gpuName: string;
  vram: string;
  queueDepth: number;
  cpu: string;
  status: string;
};

export type DashboardSnapshot = {
  quickActions: string[];
  printers: PrinterSummary[];
  compatibilityChecks: CompatibilityCheck[];
  aiUsage: AiUsageSummary;
  resources: ResourceSnapshot;
};
