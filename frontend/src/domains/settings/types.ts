export type ProviderSecretStatus = {
  provider: string;
  secretName: string;
  label: string;
  purpose: string;
  configured: boolean;
  maskedValue: string | null;
  updatedAt: string | null;
};
