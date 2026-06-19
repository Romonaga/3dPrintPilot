export type AiAccountingStatus = {
  estimatedCostSupported: boolean;
  finalCostSupported: boolean;
  reconciliationRequired: boolean;
  reusablePackage: string;
  openAiApiTokenConfigured: boolean;
  openAiAccountKeyConfigured: boolean;
  openAiFallbackEnabled: boolean;
  localModel: string;
  openAiFallbackModel: string;
  qualityThreshold: number;
  monthlyBudgetUsd: string;
  singleRequestBudgetUsd: string;
  estimatedMonthToDateUsd: string;
  budgetRemainingUsd: string;
};

export type CostReconciliationRun = {
  runId: string;
  status: string;
  periodStart: string;
  periodEnd: string;
  startedAt: string;
  finishedAt: string | null;
  estimatedTotalUsd: string;
  finalTotalUsd: string | null;
  details: Record<string, unknown>;
};

export type CostReconciliationResult = {
  runId: string;
  status: string;
  periodStart: string;
  periodEnd: string;
  estimatedTotalUsd: string;
  finalTotalUsd: string | null;
  eventCount: number;
  updatedEventCount: number;
  bucketCount: number;
};
