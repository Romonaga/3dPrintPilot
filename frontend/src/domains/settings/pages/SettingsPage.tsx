import { AlertTriangle, CheckCircle2, Download, ExternalLink, Globe2, KeyRound, RefreshCw, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { StatusBadge } from "../../../components/StatusBadge";
import { downloadOperationsBackup } from "../../operations/api";
import { ResourceControlsPanel } from "../../resources/components/ResourceControlsPanel";
import { getFeatureSettings } from "../api/settingsApi";
import { useModelSourceAuth } from "../hooks/useModelSourceAuth";
import { useProviderSecrets } from "../hooks/useProviderSecrets";
import { type FeatureSettings, type ModelSourceSiteStatus, type ProviderSecretStatus } from "../types";

export default function SettingsPage() {
  const { secrets, isLoading, isSaving, error, reload, saveSecret, removeSecret } = useProviderSecrets();
  const sourceAuth = useModelSourceAuth();
  const [features, setFeatures] = useState<FeatureSettings | null>(null);
  const [featureError, setFeatureError] = useState<string | null>(null);
  const [backupError, setBackupError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);

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

  return (
    <section className="settings-page">
      <ResourceControlsPanel />
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
              onDisconnect={() => sourceAuth.disconnectSiteAuth(site.siteKey)}
              onSave={(input) => sourceAuth.saveSiteAuth(site.siteKey, input)}
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

type SourceSiteAuthRowProps = {
  site: ModelSourceSiteStatus;
  isSaving: boolean;
  onSave: (input: {
    authMode: string;
    secretValue?: string | null;
    label?: string | null;
    accountIdentifier?: string | null;
    headerName?: string | null;
    enabled?: boolean;
  }) => Promise<void>;
  onDisconnect: () => Promise<void>;
};

function SourceSiteAuthRow({ site, isSaving, onSave, onDisconnect }: SourceSiteAuthRowProps) {
  const initialMode = site.authProfile.authMode === "none" ? site.supportedAuthModes[0] ?? "none" : site.authProfile.authMode;
  const [authMode, setAuthMode] = useState(initialMode);
  const [accountIdentifier, setAccountIdentifier] = useState(site.authProfile.accountIdentifier ?? "");
  const [label, setLabel] = useState(site.authProfile.label ?? "");
  const [headerName, setHeaderName] = useState(site.authProfile.headerName ?? "");
  const [secretValue, setSecretValue] = useState("");
  const requiresAccountIdentifier = authMode === "username_password" || authMode === "browser_session";
  const requiresSecret = ["api_token", "bearer_token", "cookie_header", "username_password"].includes(authMode);
  const canSave =
    authMode === "none" ||
    ((!requiresAccountIdentifier || accountIdentifier.trim().length > 0) &&
      (!requiresSecret || secretValue.trim().length > 0) &&
      (authMode !== "api_token" || headerName.trim().length > 0));

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSave({
      authMode,
      accountIdentifier: accountIdentifier.trim() || null,
      headerName: headerName.trim() || null,
      label: label.trim() || null,
      secretValue: secretValue.trim() || null,
      enabled: true
    });
    setSecretValue("");
  }

  return (
    <article className="source-site-row">
      <div className="source-site-heading">
        <Globe2 size={18} aria-hidden="true" />
        <div>
          <h3>{site.displayName}</h3>
          <p>{site.baseUrl ?? site.allowedHosts.join(", ")}</p>
        </div>
      </div>

      <div className="secret-status">
        <StatusBadge
          icon={site.authProfile.configured ? CheckCircle2 : AlertTriangle}
          label={site.authProfile.configured ? "Linked" : authMode === "browser_session" ? "Browser flow" : "Not linked"}
          tone={site.authProfile.configured ? "ok" : "warn"}
        />
        <span>{site.authProfile.maskedAccountIdentifier ?? site.authProfile.maskedValue ?? "No credential stored"}</span>
        {site.loginUrl ? (
          <a className="inline-link" href={site.loginUrl} rel="noreferrer" target="_blank">
            <ExternalLink size={14} aria-hidden="true" />
            <span>Open login</span>
          </a>
        ) : null}
      </div>

      {site.authStorageNotes ? <p className="muted-copy">{site.authStorageNotes}</p> : null}

      <form className="source-site-form" onSubmit={handleSubmit}>
        <label className="field-label">
          Auth type
          <select value={authMode} onChange={(event) => setAuthMode(event.target.value)}>
            {site.supportedAuthModes.map((mode) => (
              <option key={mode} value={mode}>
                {authModeLabel(mode)}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          Label
          <input
            autoComplete="off"
            onChange={(event) => setLabel(event.target.value)}
            placeholder="Personal account"
            type="text"
            value={label}
          />
        </label>
        {requiresAccountIdentifier ? (
          <label className="field-label">
            Account
            <input
              autoComplete="username"
              onChange={(event) => setAccountIdentifier(event.target.value)}
              placeholder="account email"
              type="email"
              value={accountIdentifier}
            />
          </label>
        ) : null}
        {authMode === "api_token" ? (
          <label className="field-label">
            Header
            <input
              autoComplete="off"
              onChange={(event) => setHeaderName(event.target.value)}
              placeholder="X-Api-Key"
              type="text"
              value={headerName}
            />
          </label>
        ) : null}
        {authMode === "username_password" ? (
          <label className="field-label">
            Printables password
            <input
              autoComplete="current-password"
              onChange={(event) => setSecretValue(event.target.value)}
              placeholder={site.authProfile.configured ? "Replace stored password" : "Password"}
              type="password"
              value={secretValue}
            />
          </label>
        ) : null}
        {authMode === "browser_session" ? (
          <label className="field-label">
            Session cookie/header
            <input
              autoComplete="off"
              onChange={(event) => setSecretValue(event.target.value)}
              placeholder="Optional encrypted session value"
              type="password"
              value={secretValue}
            />
          </label>
        ) : null}
        {["api_token", "bearer_token", "cookie_header"].includes(authMode) ? (
          <label className="field-label">
            Secret
            <input
              autoComplete="off"
              onChange={(event) => setSecretValue(event.target.value)}
              placeholder="Secret value"
              type="password"
              value={secretValue}
            />
          </label>
        ) : null}
        <div className="source-site-actions">
          <button className="primary-action icon-action" type="submit" disabled={isSaving || !canSave}>
            {isSaving ? <Spinner size={15} /> : null}
            <span>{isSaving ? "Saving" : "Save"}</span>
          </button>
          <button
            className="text-button icon-action"
            disabled={isSaving || site.authProfile.authMode === "none"}
            onClick={onDisconnect}
            type="button"
          >
            {isSaving ? <Spinner size={15} /> : <Trash2 size={15} aria-hidden="true" />}
            <span>Disconnect</span>
          </button>
        </div>
      </form>
    </article>
  );
}

function authModeLabel(mode: string) {
  const labels: Record<string, string> = {
    none: "None",
    api_token: "API token",
    bearer_token: "Bearer token",
    cookie_header: "Cookie header",
    username_password: "Email and password",
    browser_session: "Browser session"
  };
  return labels[mode] ?? mode;
}

type SecretRowProps = {
  secret: ProviderSecretStatus;
  isSaving: boolean;
  onSave: (value: string) => Promise<void>;
  onRemove: () => Promise<void>;
};

function SecretRow({ secret, isSaving, onSave, onRemove }: SecretRowProps) {
  const [value, setValue] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSave(value);
    setValue("");
  }

  return (
    <article className="secret-row">
      <div className="secret-heading">
        <KeyRound size={18} aria-hidden="true" />
        <div>
          <h3>{secret.label}</h3>
          <p>{secret.purpose}</p>
        </div>
      </div>

      <div className="secret-status">
        <StatusBadge
          icon={secret.configured ? CheckCircle2 : AlertTriangle}
          label={secret.configured ? "Configured" : "Missing"}
          tone={secret.configured ? "ok" : "warn"}
        />
        <span>{secret.maskedValue ?? "Not stored"}</span>
      </div>

      <form className="secret-form" onSubmit={handleSubmit}>
        <label className="field-label">
          New value
          <input
            autoComplete="off"
            onChange={(event) => setValue(event.target.value)}
            placeholder="Paste key"
            type="password"
            value={value}
          />
        </label>
        <button className="primary-action icon-action" type="submit" disabled={isSaving || value.trim().length === 0}>
          {isSaving ? <Spinner size={15} /> : null}
          <span>{isSaving ? "Saving" : "Save"}</span>
        </button>
        <button
          aria-label={`Remove ${secret.label}`}
          className="icon-only-button"
          disabled={isSaving || !secret.configured}
          onClick={onRemove}
          title={`Remove ${secret.label}`}
          type="button"
        >
          {isSaving ? <Spinner size={16} /> : <Trash2 size={16} aria-hidden="true" />}
        </button>
      </form>
    </article>
  );
}
