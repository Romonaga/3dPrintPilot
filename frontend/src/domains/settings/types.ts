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
  authReady: boolean;
  linkStatus: string;
  linkStatusMessage: string;
  maskedValue: string | null;
  updatedAt: string | null;
};

export type ModelSourceSiteStatus = {
  siteKey: string;
  displayName: string;
  supportLevel: string;
  capabilities: string[];
  setupRequired: boolean;
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

export type SourceAuthLinkInstructions = {
  siteKey: string;
  displayName: string;
  authMode: string;
  loginUrl: string | null;
  accountIdentifier: string | null;
  instructions: string[];
  storageNotes: string;
};

export type SourceAuthBrowserLinkStatus = {
  siteKey: string;
  displayName: string;
  authMode: string;
  sessionId: string;
  status: string;
  message: string;
  loginUrl: string | null;
  expiresAt: string;
  cookieCount: number;
  authProfile: SourceAuthProfileStatus | null;
};

export type SourceAuthReadinessStatus = {
  siteKey: string;
  displayName: string;
  authMode: string;
  authReady: boolean;
  linkStatus: string;
  message: string;
  configured: boolean;
  enabled: boolean;
  maskedAccountIdentifier: string | null;
  maskedValue: string | null;
  updatedAt: string | null;
};
