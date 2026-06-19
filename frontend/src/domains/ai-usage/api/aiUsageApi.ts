import {
  type AiAccountingStatus,
  type CostReconciliationResult,
  type CostReconciliationRun
} from "../types";
import { apiFetch } from "../../../lib/apiFetch";

type ApiAccountingStatus = {
  estimated_cost_supported: boolean;
  final_cost_supported: boolean;
  reconciliation_required: boolean;
  reusable_package: string;
  openai_api_token_configured: boolean;
  openai_account_key_configured: boolean;
};

type ApiReconciliationRun = {
  run_id: string;
  status: string;
  period_start: string;
  period_end: string;
  started_at: string;
  finished_at: string | null;
  estimated_total_usd: string;
  final_total_usd: string | null;
  details: Record<string, unknown>;
};

type ApiReconciliationResult = {
  run_id: string;
  status: string;
  period_start: string;
  period_end: string;
  estimated_total_usd: string;
  final_total_usd: string | null;
  event_count: number;
  updated_event_count: number;
  bucket_count: number;
};

export async function getAiAccountingStatus(): Promise<AiAccountingStatus> {
  const response = await apiFetch("/api/ai/accounting/status");
  if (!response.ok) {
    throw new Error(`AI accounting status failed with HTTP ${response.status}`);
  }
  return fromApiStatus(await response.json());
}

export async function listReconciliationRuns(): Promise<CostReconciliationRun[]> {
  const response = await apiFetch("/api/ai/accounting/reconciliation-runs");
  if (!response.ok) {
    throw new Error(`Reconciliation run list failed with HTTP ${response.status}`);
  }
  const runs = (await response.json()) as ApiReconciliationRun[];
  return runs.map(fromApiRun);
}

export async function reconcileOpenAiCosts(periodStart: string, periodEnd: string): Promise<CostReconciliationResult> {
  const response = await apiFetch("/api/ai/accounting/reconcile/openai", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      period_start: new Date(`${periodStart}T00:00:00`).toISOString(),
      period_end: new Date(`${periodEnd}T00:00:00`).toISOString()
    })
  });
  if (!response.ok) {
    throw new Error(`OpenAI reconciliation failed with HTTP ${response.status}`);
  }
  return fromApiResult(await response.json());
}

function fromApiStatus(status: ApiAccountingStatus): AiAccountingStatus {
  return {
    estimatedCostSupported: status.estimated_cost_supported,
    finalCostSupported: status.final_cost_supported,
    reconciliationRequired: status.reconciliation_required,
    reusablePackage: status.reusable_package,
    openAiApiTokenConfigured: status.openai_api_token_configured,
    openAiAccountKeyConfigured: status.openai_account_key_configured
  };
}

function fromApiRun(run: ApiReconciliationRun): CostReconciliationRun {
  return {
    runId: run.run_id,
    status: run.status,
    periodStart: run.period_start,
    periodEnd: run.period_end,
    startedAt: run.started_at,
    finishedAt: run.finished_at,
    estimatedTotalUsd: run.estimated_total_usd,
    finalTotalUsd: run.final_total_usd,
    details: run.details
  };
}

function fromApiResult(result: ApiReconciliationResult): CostReconciliationResult {
  return {
    runId: result.run_id,
    status: result.status,
    periodStart: result.period_start,
    periodEnd: result.period_end,
    estimatedTotalUsd: result.estimated_total_usd,
    finalTotalUsd: result.final_total_usd,
    eventCount: result.event_count,
    updatedEventCount: result.updated_event_count,
    bucketCount: result.bucket_count
  };
}
