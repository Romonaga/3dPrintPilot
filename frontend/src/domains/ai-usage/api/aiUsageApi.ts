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
  openai_fallback_enabled: boolean;
  local_model: string;
  openai_fallback_model: string;
  quality_threshold: number;
  monthly_budget_usd: string;
  single_request_budget_usd: string;
  estimated_month_to_date_usd: string;
  budget_remaining_usd: string;
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
  const startIso = dateInputToIso(periodStart, "start");
  const endIso = dateInputToIso(periodEnd, "end");
  if (new Date(endIso).getTime() <= new Date(startIso).getTime()) {
    throw new Error("Reconciliation end date must be after start date");
  }
  const response = await apiFetch("/api/ai/accounting/reconcile/openai", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      period_start: startIso,
      period_end: endIso
    })
  });
  if (!response.ok) {
    throw new Error(`OpenAI reconciliation failed with HTTP ${response.status}`);
  }
  return fromApiResult(await response.json());
}

function dateInputToIso(value: string, label: "start" | "end") {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    throw new Error(`Invalid reconciliation ${label} date`);
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    throw new Error(`Invalid reconciliation ${label} date`);
  }
  return date.toISOString();
}

function fromApiStatus(status: ApiAccountingStatus): AiAccountingStatus {
  return {
    estimatedCostSupported: status.estimated_cost_supported,
    finalCostSupported: status.final_cost_supported,
    reconciliationRequired: status.reconciliation_required,
    reusablePackage: status.reusable_package,
    openAiApiTokenConfigured: status.openai_api_token_configured,
    openAiAccountKeyConfigured: status.openai_account_key_configured,
    openAiFallbackEnabled: status.openai_fallback_enabled,
    localModel: status.local_model,
    openAiFallbackModel: status.openai_fallback_model,
    qualityThreshold: status.quality_threshold,
    monthlyBudgetUsd: status.monthly_budget_usd,
    singleRequestBudgetUsd: status.single_request_budget_usd,
    estimatedMonthToDateUsd: status.estimated_month_to_date_usd,
    budgetRemainingUsd: status.budget_remaining_usd
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
