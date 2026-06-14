import { useCallback, useEffect, useState } from "react";
import { deleteProviderSecret, listProviderSecrets, saveProviderSecret } from "../api/settingsApi";
import { type ProviderSecretStatus } from "../types";

export function useProviderSecrets() {
  const [secrets, setSecrets] = useState<ProviderSecretStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSecrets = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setSecrets(await listProviderSecrets());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Provider secret status failed");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSecrets();
  }, [loadSecrets]);

  async function saveSecret(secret: ProviderSecretStatus, value: string) {
    setIsSaving(`${secret.provider}:${secret.secretName}`);
    setError(null);
    try {
      const updated = await saveProviderSecret(secret.provider, secret.secretName, value);
      setSecrets((current) =>
        current.map((candidate) =>
          candidate.provider === updated.provider && candidate.secretName === updated.secretName ? updated : candidate
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Provider secret save failed");
    } finally {
      setIsSaving(null);
    }
  }

  async function removeSecret(secret: ProviderSecretStatus) {
    setIsSaving(`${secret.provider}:${secret.secretName}`);
    setError(null);
    try {
      await deleteProviderSecret(secret.provider, secret.secretName);
      await loadSecrets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Provider secret delete failed");
    } finally {
      setIsSaving(null);
    }
  }

  return { secrets, isLoading, isSaving, error, reload: loadSecrets, saveSecret, removeSecret };
}
