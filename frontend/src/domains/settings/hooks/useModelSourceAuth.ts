import { useCallback, useEffect, useState } from "react";
import {
  deleteSourceAuthProfile,
  listModelSourceSites,
  saveSourceAuthProfile,
  startSourceAuthLink,
  testSourceAuthProfile
} from "../api/settingsApi";
import {
  type ModelSourceSiteStatus,
  type SaveSourceAuthProfileInput,
  type SourceAuthLinkInstructions
} from "../types";

export function useModelSourceAuth() {
  const [sites, setSites] = useState<ModelSourceSiteStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState<string | null>(null);
  const [linkInstructions, setLinkInstructions] = useState<Record<string, SourceAuthLinkInstructions>>({});
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

  async function startBrowserLink(siteKey: string) {
    setIsSaving(siteKey);
    setError(null);
    try {
      const instructions = await startSourceAuthLink(siteKey);
      setLinkInstructions((current) => ({ ...current, [siteKey]: instructions }));
      if (instructions.loginUrl) {
        window.open(instructions.loginUrl, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Model source auth link failed");
    } finally {
      setIsSaving(null);
    }
  }

  async function testSiteAuth(siteKey: string) {
    setIsTesting(siteKey);
    setError(null);
    try {
      const readiness = await testSourceAuthProfile(siteKey);
      setSites((current) =>
        current.map((site) =>
          site.siteKey === siteKey
            ? {
                ...site,
                authProfile: {
                  ...site.authProfile,
                  authMode: readiness.authMode,
                  authReady: readiness.authReady,
                  linkStatus: readiness.linkStatus,
                  linkStatusMessage: readiness.message,
                  configured: readiness.configured,
                  enabled: readiness.enabled,
                  maskedAccountIdentifier: readiness.maskedAccountIdentifier,
                  maskedValue: readiness.maskedValue,
                  updatedAt: readiness.updatedAt
                }
              }
            : site
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Model source auth test failed");
    } finally {
      setIsTesting(null);
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

  return {
    sites,
    isLoading,
    isSaving,
    isTesting,
    linkInstructions,
    error,
    reload: loadSites,
    saveSiteAuth,
    startBrowserLink,
    testSiteAuth,
    disconnectSiteAuth
  };
}
