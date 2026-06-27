import { AlertTriangle, CheckCircle2, Clock, Download, RefreshCw, Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { StatusBadge } from "../../../components/StatusBadge";
import { downloadOperationsBackup } from "../../operations/api";
import { ResourceControlsPanel } from "../../resources/components/ResourceControlsPanel";
import { getAuthSettings, getFeatureSettings, saveAuthSettings } from "../api/settingsApi";
import { useModelSourceAuth } from "../hooks/useModelSourceAuth";
import { useProviderSecrets } from "../hooks/useProviderSecrets";
import { type AuthSettings, type FeatureSettings } from "../types";
import { type AuthUser } from "../../auth/types";
import { SecretRow } from "../components/SecretRow";
import { SourceSiteAuthRow } from "../components/SourceSiteAuthRow";

type SettingsPageProps = {
  user: AuthUser;
};

export default function SettingsPage({ user }: SettingsPageProps) {
  const { secrets, isLoading, isSaving, error, reload, saveSecret, removeSecret } = useProviderSecrets();
  const sourceAuth = useModelSourceAuth();
  const [features, setFeatures] = useState<FeatureSettings | null>(null);
  const [featureError, setFeatureError] = useState<string | null>(null);
  const [authSettings, setAuthSettings] = useState<AuthSettings | null>(null);
  const [authSettingsValue, setAuthSettingsValue] = useState("");
  const [authSettingsError, setAuthSettingsError] = useState<string | null>(null);
  const [isSavingAuthSettings, setIsSavingAuthSettings] = useState(false);
  const [backupError, setBackupError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const canManageAuthSettings = user.role === "owner" || user.role === "admin";

  useEffect(() => {
    let active = true;
    getFeatureSettings()
      .then((settings) => {
        if (active) {
          setFeatures(settings);
          setFeatureError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setFeatureError(err instanceof Error ? err.message : "Feature settings failed");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!canManageAuthSettings) {
      return;
    }
    let active = true;
    getAuthSettings()
      .then((settings) => {
        if (active) {
          setAuthSettings(settings);
          setAuthSettingsValue(String(settings.sessionTimeoutMinutes));
          setAuthSettingsError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setAuthSettingsError(err instanceof Error ? err.message : "Auth settings failed");
        }
      });
    return () => {
      active = false;
    };
  }, [canManageAuthSettings]);

  async function handleBackupExport() {
    setIsExporting(true);
    try {
      await downloadOperationsBackup();
      setBackupError(null);
    } catch (err) {
      setBackupError(err instanceof Error ? err.message : "Backup export failed");
    } finally {
      setIsExporting(false);
    }
  }

  async function handleAuthSettingsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authSettings) {
      return;
    }
    const nextTimeout = Number(authSettingsValue);
    if (!Number.isInteger(nextTimeout)) {
      setAuthSettingsError("Session timeout must be a whole number of minutes");
      return;
    }
    setIsSavingAuthSettings(true);
    setAuthSettingsError(null);
    try {
      const updated = await saveAuthSettings(nextTimeout);
      setAuthSettings(updated);
      setAuthSettingsValue(String(updated.sessionTimeoutMinutes));
    } catch (err) {
      setAuthSettingsError(err instanceof Error ? err.message : "Auth settings save failed");
    } finally {
      setIsSavingAuthSettings(false);
    }
  }

  return (
    <section className="settings-page">
      <ResourceControlsPanel />
      {canManageAuthSettings ? (
        <article className="panel">
          <div className="panel-header">
            <div>
              <h2>Session Timeout</h2>
              {authSettingsError ? <p className="form-error">{authSettingsError}</p> : null}
            </div>
            {authSettings ? (
              <StatusBadge
                icon={Clock}
                label={`${authSettings.sessionTimeoutMinutes} min`}
                tone="muted"
              />
            ) : null}
          </div>
          {authSettings ? (
            <form className="secret-form auth-settings-form" onSubmit={handleAuthSettingsSubmit}>
              <label className="field-label">
                Minutes
                <input
                  max={authSettings.maxSessionTimeoutMinutes}
                  min={authSettings.minSessionTimeoutMinutes}
                  onChange={(event) => setAuthSettingsValue(event.target.value)}
                  step={1}
                  type="number"
                  value={authSettingsValue}
                />
              </label>
              <button className="primary-action icon-action" disabled={isSavingAuthSettings} type="submit">
                {isSavingAuthSettings ? <Spinner size={15} /> : <Save size={15} aria-hidden="true" />}
                <span>{isSavingAuthSettings ? "Saving" : "Save"}</span>
              </button>
            </form>
          ) : null}
        </article>
      ) : null}
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>Model Source Accounts</h2>
            {sourceAuth.error ? <p className="form-error">{sourceAuth.error}</p> : null}
          </div>
          <button className="text-button icon-action" type="button" onClick={sourceAuth.reload} disabled={sourceAuth.isLoading}>
            {sourceAuth.isLoading ? <Spinner size={15} /> : <RefreshCw size={15} aria-hidden="true" />}
            <span>Refresh</span>
          </button>
        </div>
        <div className="source-site-list">
          {sourceAuth.sites.map((site) => (
            <SourceSiteAuthRow
              key={site.siteKey}
              isSaving={sourceAuth.isSaving === site.siteKey}
              isTesting={sourceAuth.isTesting === site.siteKey}
              browserLink={sourceAuth.browserLinks[site.siteKey] ?? null}
              linkInstructions={sourceAuth.linkInstructions[site.siteKey] ?? null}
              onCaptureBrowserLink={() => sourceAuth.captureAssistedBrowserLink(site.siteKey)}
              onDisconnect={() => sourceAuth.disconnectSiteAuth(site.siteKey)}
              onRefreshBrowserLink={() => sourceAuth.refreshAssistedBrowserLink(site.siteKey)}
              onSave={(input) => sourceAuth.saveSiteAuth(site.siteKey, input)}
              onStartBrowserLink={(input) => sourceAuth.startAssistedBrowserLink(site.siteKey, input)}
              onStartManualLink={() => sourceAuth.startBrowserLink(site.siteKey)}
              onTest={() => sourceAuth.testSiteAuth(site.siteKey)}
              site={site}
            />
          ))}
          {sourceAuth.isLoading ? <p className="muted-copy">Loading model source account status.</p> : null}
        </div>
      </article>
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>Operations</h2>
            {backupError ? <p className="form-error">{backupError}</p> : null}
          </div>
          <button className="primary-action icon-action" type="button" onClick={handleBackupExport} disabled={isExporting}>
            {isExporting ? <Spinner size={15} /> : <Download size={15} aria-hidden="true" />}
            <span>{isExporting ? "Exporting" : "Export Backup"}</span>
          </button>
        </div>
      </article>
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>AI Settings</h2>
            {featureError ? <p className="form-error">{featureError}</p> : null}
          </div>
          {features ? (
            <StatusBadge
              icon={features.openAiFallbackEnabled ? CheckCircle2 : AlertTriangle}
              label={features.openAiFallbackEnabled ? "Fallback enabled" : "Fallback disabled"}
              tone={features.openAiFallbackEnabled ? "ok" : "warn"}
            />
          ) : null}
        </div>
        {features ? (
          <dl className="metric-grid settings-metric-grid">
            <div>
              <dt>Local AI</dt>
              <dd>
                {features.localAiProvider} / {features.localAiDefaultModel}
              </dd>
            </div>
            <div>
              <dt>OpenAI Model</dt>
              <dd>{features.openAiFallbackModel}</dd>
            </div>
            <div>
              <dt>Quality Gate</dt>
              <dd>{features.aiQualityThreshold}</dd>
            </div>
            <div>
              <dt>Monthly Budget</dt>
              <dd>${features.openAiMonthlyBudgetUsd}</dd>
            </div>
            <div>
              <dt>Request Budget</dt>
              <dd>${features.openAiSingleRequestBudgetUsd}</dd>
            </div>
            <div>
              <dt>Cost Reconcile</dt>
              <dd>{features.costReconciliationRequired ? "Required" : "Optional"}</dd>
            </div>
          </dl>
        ) : null}
      </article>
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>Provider Secrets</h2>
            {error ? <p className="form-error">{error}</p> : null}
          </div>
          <button className="text-button icon-action" type="button" onClick={reload} disabled={isLoading}>
            {isLoading ? <Spinner size={15} /> : <RefreshCw size={15} aria-hidden="true" />}
            <span>Refresh</span>
          </button>
        </div>

        <div className="secret-list">
          {secrets.map((secret) => (
            <SecretRow
              key={`${secret.provider}:${secret.secretName}`}
              secret={secret}
              isSaving={isSaving === `${secret.provider}:${secret.secretName}`}
              onRemove={() => removeSecret(secret)}
              onSave={(value) => saveSecret(secret, value)}
            />
          ))}
          {isLoading ? <p className="muted-copy">Loading provider secret status.</p> : null}
        </div>
      </article>
    </section>
  );
}
