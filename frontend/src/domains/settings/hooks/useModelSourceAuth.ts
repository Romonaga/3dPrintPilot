import { useCallback, useEffect, useState } from "react";
import {
  captureSourceAuthBrowserLink,
  deleteSourceAuthProfile,
  getSourceAuthBrowserLinkStatus,
  listModelSourceSites,
  saveSourceAuthProfile,
  startSourceAuthBrowserLink,
  startSourceAuthLink,
  testSourceAuthProfile
} from "../api/settingsApi";
import {
  type SourceAuthBrowserLinkStatus,
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
  const [browserLinks, setBrowserLinks] = useState<Record<string, SourceAuthBrowserLinkStatus>>({});
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

  useEffect(() => {
    const activeLinks = Object.values(browserLinks).filter((link) =>
      ["running", "capture_requested"].includes(link.status)
    );
    if (activeLinks.length === 0) {
      return;
    }

    let canceled = false;
    const interval = window.setInterval(() => {
      for (const activeLink of activeLinks) {
        void getSourceAuthBrowserLinkStatus(activeLink.siteKey, activeLink.sessionId)
          .then((link) => {
            if (canceled) {
              return;
            }
            setBrowserLinks((current) => ({ ...current, [link.siteKey]: link }));
            applyBrowserLinkProfile(link);
          })
          .catch((err) => {
            if (!canceled) {
              setError(err instanceof Error ? err.message : "Browser link status failed");
            }
          });
      }
    }, 2500);

    return () => {
      canceled = true;
      window.clearInterval(interval);
    };
  }, [browserLinks]);

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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Model source auth link failed");
    } finally {
      setIsSaving(null);
    }
  }

  async function startAssistedBrowserLink(siteKey: string, input: { label?: string | null; accountIdentifier?: string | null }) {
    setIsSaving(siteKey);
    setError(null);
    try {
      const link = await startSourceAuthBrowserLink(siteKey, input);
      setBrowserLinks((current) => ({ ...current, [siteKey]: link }));
      applyBrowserLinkProfile(link);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Browser link start failed");
    } finally {
      setIsSaving(null);
    }
  }

  async function captureAssistedBrowserLink(siteKey: string) {
    const sessionId = browserLinks[siteKey]?.sessionId;
    if (!sessionId) {
      setError("Start browser linking before capturing the session");
      return;
    }
    setIsSaving(siteKey);
    setError(null);
    try {
      const link = await captureSourceAuthBrowserLink(siteKey, sessionId);
      setBrowserLinks((current) => ({ ...current, [siteKey]: link }));
      applyBrowserLinkProfile(link);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Browser link capture failed");
    } finally {
      setIsSaving(null);
    }
  }

  async function refreshAssistedBrowserLink(siteKey: string) {
    const sessionId = browserLinks[siteKey]?.sessionId;
    if (!sessionId) {
      return;
    }
    setIsTesting(siteKey);
    setError(null);
    try {
      const link = await getSourceAuthBrowserLinkStatus(siteKey, sessionId);
      setBrowserLinks((current) => ({ ...current, [siteKey]: link }));
      applyBrowserLinkProfile(link);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Browser link status failed");
    } finally {
      setIsTesting(null);
    }
  }

  function applyBrowserLinkProfile(link: SourceAuthBrowserLinkStatus) {
    if (!link.authProfile) {
      return;
    }
    setSites((current) =>
      current.map((site) => (site.siteKey === link.siteKey ? { ...site, authProfile: link.authProfile ?? site.authProfile } : site))
    );
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
    browserLinks,
    error,
    reload: loadSites,
    saveSiteAuth,
    startBrowserLink,
    startAssistedBrowserLink,
    captureAssistedBrowserLink,
    refreshAssistedBrowserLink,
    testSiteAuth,
    disconnectSiteAuth
  };
}
