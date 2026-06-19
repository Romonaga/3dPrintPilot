export type ProviderSecretStatus = {
  provider: string;
  secretName: string;
  label: string;
  purpose: string;
  configured: boolean;
  maskedValue: string | null;
  updatedAt: string | null;
};

export type FeatureSettings = {
  openAiFallbackEnabled: boolean;
  openAiFallbackModel: string;
  aiQualityThreshold: number;
  openAiMonthlyBudgetUsd: string;
  openAiSingleRequestBudgetUsd: string;
  costReconciliationRequired: boolean;
  localAiProvider: string;
  localAiDefaultModel: string;
};
