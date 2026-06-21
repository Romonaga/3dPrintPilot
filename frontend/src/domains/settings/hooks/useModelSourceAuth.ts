import { useCallback, useEffect, useState } from "react";
import { deleteSourceAuthProfile, listModelSourceSites, saveSourceAuthProfile } from "../api/settingsApi";
import { type ModelSourceSiteStatus, type SaveSourceAuthProfileInput } from "../types";

export function useModelSourceAuth() {
  const [sites, setSites] = useState<ModelSourceSiteStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSites = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setSites(await listModelSourceSites());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Model source auth status failed");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSites();
  }, [loadSites]);

  async function saveSiteAuth(siteKey: string, input: SaveSourceAuthProfileInput) {
    setIsSaving(siteKey);
    setError(null);
    try {
      const updated = await saveSourceAuthProfile(siteKey, input);
      setSites((current) =>
        current.map((site) => (site.siteKey === siteKey ? { ...site, authProfile: updated } : site))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Model source auth save failed");
    } finally {
      setIsSaving(null);
    }
  }

  async function disconnectSiteAuth(siteKey: string) {
    setIsSaving(siteKey);
    setError(null);
    try {
      await deleteSourceAuthProfile(siteKey);
      await loadSites();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Model source auth disconnect failed");
    } finally {
      setIsSaving(null);
    }
  }

  return { sites, isLoading, isSaving, error, reload: loadSites, saveSiteAuth, disconnectSiteAuth };
}
