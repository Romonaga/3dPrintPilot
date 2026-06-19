import { apiFetch } from "../../../lib/apiFetch";
import { type FeatureSettings, type ProviderSecretStatus } from "../types";

type ApiProviderSecretStatus = {
  provider: string;
  secret_name: string;
  label: string;
  purpose: string;
  configured: boolean;
  masked_value: string | null;
  updated_at: string | null;
};

type ApiFeatureSettings = {
  openai_fallback_enabled: boolean;
  openai_fallback_model: string;
  ai_quality_threshold: number;
  openai_monthly_budget_usd: string;
  openai_single_request_budget_usd: string;
  cost_reconciliation_required: boolean;
  local_ai_provider: string;
  local_ai_default_model: string;
};

export async function getFeatureSettings(): Promise<FeatureSettings> {
  const response = await apiFetch("/api/settings/features");
  if (!response.ok) {
    throw new Error(`Feature settings failed with HTTP ${response.status}`);
  }
  return fromApiFeatureSettings((await response.json()) as ApiFeatureSettings);
}

export async function listProviderSecrets(): Promise<ProviderSecretStatus[]> {
  const response = await apiFetch("/api/settings/provider-secrets");
  if (!response.ok) {
    throw new Error(`Provider secret status failed with HTTP ${response.status}`);
  }
  const secrets = (await response.json()) as ApiProviderSecretStatus[];
  return secrets.map(fromApiSecret);
}

export async function saveProviderSecret(provider: string, secretName: string, value: string) {
  const response = await apiFetch(`/api/settings/provider-secrets/${provider}/${secretName}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value })
  });
  if (!response.ok) {
    throw new Error(`Provider secret save failed with HTTP ${response.status}`);
  }
  return fromApiSecret(await response.json());
}

export async function deleteProviderSecret(provider: string, secretName: string) {
  const response = await apiFetch(`/api/settings/provider-secrets/${provider}/${secretName}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`Provider secret delete failed with HTTP ${response.status}`);
  }
}

function fromApiSecret(secret: ApiProviderSecretStatus): ProviderSecretStatus {
  return {
    provider: secret.provider,
    secretName: secret.secret_name,
    label: secret.label,
    purpose: secret.purpose,
    configured: secret.configured,
    maskedValue: secret.masked_value,
    updatedAt: secret.updated_at
  };
}

function fromApiFeatureSettings(settings: ApiFeatureSettings): FeatureSettings {
  return {
    openAiFallbackEnabled: settings.openai_fallback_enabled,
    openAiFallbackModel: settings.openai_fallback_model,
    aiQualityThreshold: settings.ai_quality_threshold,
    openAiMonthlyBudgetUsd: settings.openai_monthly_budget_usd,
    openAiSingleRequestBudgetUsd: settings.openai_single_request_budget_usd,
    costReconciliationRequired: settings.cost_reconciliation_required,
    localAiProvider: settings.local_ai_provider,
    localAiDefaultModel: settings.local_ai_default_model
  };
}
