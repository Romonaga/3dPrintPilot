import { apiFetch } from "../../../lib/apiFetch";
import {
  type FeatureSettings,
  type ModelSourceSiteStatus,
  type ProviderSecretStatus,
  type SaveSourceAuthProfileInput,
  type SourceAuthProfileStatus
} from "../types";

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

type ApiSiteAdapter = {
  site_key: string;
  display_name: string;
  base_url: string | null;
  login_url: string | null;
  enabled: boolean;
  supports_downloads: boolean;
  supported_auth_modes: string[];
  auth_storage_notes: string | null;
  allowed_hosts: string[];
  default_limits: Record<string, unknown>;
  robots_terms_notes: string | null;
};

type ApiSourceAuthProfile = {
  site_key: string;
  display_name: string;
  auth_mode: string;
  label: string | null;
  account_identifier: string | null;
  masked_account_identifier: string | null;
  header_name: string | null;
  configured: boolean;
  enabled: boolean;
  masked_value: string | null;
  updated_at: string | null;
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

export async function listModelSourceSites(): Promise<ModelSourceSiteStatus[]> {
  const [adapterResponse, authResponse] = await Promise.all([
    apiFetch("/api/site-scanning/adapters"),
    apiFetch("/api/site-scanning/auth-profiles")
  ]);
  if (!adapterResponse.ok) {
    throw new Error(`Model source adapter status failed with HTTP ${adapterResponse.status}`);
  }
  if (!authResponse.ok) {
    throw new Error(`Model source auth status failed with HTTP ${authResponse.status}`);
  }
  const adapters = (await adapterResponse.json()) as ApiSiteAdapter[];
  const authProfiles = ((await authResponse.json()) as ApiSourceAuthProfile[]).map(fromApiSourceAuthProfile);
  const authBySite = new Map(authProfiles.map((profile) => [profile.siteKey, profile]));
  return adapters.map((adapter) => fromApiModelSourceSite(adapter, authBySite.get(adapter.site_key)));
}

export async function saveSourceAuthProfile(
  siteKey: string,
  input: SaveSourceAuthProfileInput
): Promise<SourceAuthProfileStatus> {
  const response = await apiFetch(`/api/site-scanning/auth-profiles/${siteKey}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      auth_mode: input.authMode,
      secret_value: input.secretValue ?? null,
      label: input.label ?? null,
      account_identifier: input.accountIdentifier ?? null,
      header_name: input.headerName ?? null,
      enabled: input.enabled ?? true
    })
  });
  if (!response.ok) {
    throw new Error(`Model source auth save failed with HTTP ${response.status}`);
  }
  return fromApiSourceAuthProfile((await response.json()) as ApiSourceAuthProfile);
}

export async function deleteSourceAuthProfile(siteKey: string) {
  const response = await apiFetch(`/api/site-scanning/auth-profiles/${siteKey}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`Model source auth delete failed with HTTP ${response.status}`);
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

function fromApiSourceAuthProfile(profile: ApiSourceAuthProfile): SourceAuthProfileStatus {
  return {
    siteKey: profile.site_key,
    displayName: profile.display_name,
    authMode: profile.auth_mode,
    label: profile.label,
    accountIdentifier: profile.account_identifier,
    maskedAccountIdentifier: profile.masked_account_identifier,
    headerName: profile.header_name,
    configured: profile.configured,
    enabled: profile.enabled,
    maskedValue: profile.masked_value,
    updatedAt: profile.updated_at
  };
}

function fromApiModelSourceSite(
  adapter: ApiSiteAdapter,
  authProfile: SourceAuthProfileStatus | undefined
): ModelSourceSiteStatus {
  return {
    siteKey: adapter.site_key,
    displayName: adapter.display_name,
    baseUrl: adapter.base_url ?? null,
    loginUrl: adapter.login_url ?? null,
    enabled: adapter.enabled,
    supportsDownloads: adapter.supports_downloads,
    supportedAuthModes: adapter.supported_auth_modes ?? ["none"],
    authStorageNotes: adapter.auth_storage_notes ?? null,
    allowedHosts: adapter.allowed_hosts ?? [],
    robotsTermsNotes: adapter.robots_terms_notes ?? null,
    authProfile:
      authProfile ??
      fromApiSourceAuthProfile({
        site_key: adapter.site_key,
        display_name: adapter.display_name,
        auth_mode: "none",
        label: null,
        account_identifier: null,
        masked_account_identifier: null,
        header_name: null,
        configured: false,
        enabled: false,
        masked_value: null,
        updated_at: null
      })
  };
}
