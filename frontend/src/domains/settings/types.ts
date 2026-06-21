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

export type SourceAuthProfileStatus = {
  siteKey: string;
  displayName: string;
  authMode: string;
  label: string | null;
  accountIdentifier: string | null;
  maskedAccountIdentifier: string | null;
  headerName: string | null;
  configured: boolean;
  enabled: boolean;
  maskedValue: string | null;
  updatedAt: string | null;
};

export type ModelSourceSiteStatus = {
  siteKey: string;
  displayName: string;
  baseUrl: string | null;
  loginUrl: string | null;
  enabled: boolean;
  supportsDownloads: boolean;
  supportedAuthModes: string[];
  authStorageNotes: string | null;
  allowedHosts: string[];
  robotsTermsNotes: string | null;
  authProfile: SourceAuthProfileStatus;
};

export type SaveSourceAuthProfileInput = {
  authMode: string;
  secretValue?: string | null;
  label?: string | null;
  accountIdentifier?: string | null;
  headerName?: string | null;
  enabled?: boolean;
};
