import { type CompatibilityCheckResult, type CompatibilityRunResult } from "../types";
import { apiFetch } from "../../../lib/apiFetch";

type ApiCheck = {
  id: number;
  scan_result_id: number;
  printer_id: number;
  status: "pass" | "warning" | "fail";
  source_type: string;
  confidence_label: string;
  model_title: string;
  model_url: string;
  printer_name: string;
  duration_ms: number;
  created_at: string;
  items: Array<{
    code: string;
    severity: "pass" | "warning" | "fail";
    message: string;
  }>;
};

type ApiRun = {
  scan_run_id: number;
  printer_count: number;
  candidate_count: number;
  check_count: number;
  checks: ApiCheck[];
};

export async function runCompatibilityChecks(scanRunId: number, maxCandidates: number): Promise<CompatibilityRunResult> {
  const response = await apiFetch("/api/compatibility/checks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scan_run_id: scanRunId,
      max_candidates: maxCandidates
    })
  });
  if (!response.ok) {
    throw new Error(`Compatibility run failed with HTTP ${response.status}`);
  }
  return fromApiRun(await response.json());
}

export async function listCompatibilityChecks(): Promise<CompatibilityCheckResult[]> {
  const response = await apiFetch("/api/compatibility/checks");
  if (!response.ok) {
    throw new Error(`Compatibility list failed with HTTP ${response.status}`);
  }
  const checks = (await response.json()) as ApiCheck[];
  return checks.map(fromApiCheck);
}

function fromApiRun(run: ApiRun): CompatibilityRunResult {
  return {
    scanRunId: run.scan_run_id,
    printerCount: run.printer_count,
    candidateCount: run.candidate_count,
    checkCount: run.check_count,
    checks: run.checks.map(fromApiCheck)
  };
}

function fromApiCheck(check: ApiCheck): CompatibilityCheckResult {
  return {
    id: check.id,
    scanResultId: check.scan_result_id,
    printerId: check.printer_id,
    status: check.status,
    sourceType: check.source_type,
    confidenceLabel: check.confidence_label,
    modelTitle: check.model_title,
    modelUrl: check.model_url,
    printerName: check.printer_name,
    durationMs: check.duration_ms,
    createdAt: check.created_at,
    items: check.items
  };
}
