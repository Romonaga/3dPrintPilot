import {
  AlertTriangle,
  CheckCircle2,
  Download,
  ExternalLink,
  Globe2,
  KeyRound,
  Link2,
  RefreshCw,
  Trash2
} from "lucide-react";
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

type SourceSiteAuthRowProps = {
  site: ModelSourceSiteStatus;
  isSaving: boolean;
  isTesting: boolean;
  linkInstructions: {
    instructions: string[];
    loginUrl: string | null;
    storageNotes: string;
  } | null;
  browserLink: {
    status: string;
    message: string;
    sessionId: string;
    cookieCount: number;
  } | null;
  onSave: (input: {
    authMode: string;
    secretValue?: string | null;
    label?: string | null;
    accountIdentifier?: string | null;
    headerName?: string | null;
    enabled?: boolean;
  }) => Promise<void>;
  onStartBrowserLink: (input: { label?: string | null; accountIdentifier?: string | null }) => Promise<void>;
  onStartManualLink: () => Promise<void>;
  onCaptureBrowserLink: () => Promise<void>;
  onRefreshBrowserLink: () => Promise<void>;
  onTest: () => Promise<void>;
  onDisconnect: () => Promise<void>;
};

function SourceSiteAuthRow({
  site,
  isSaving,
  isTesting,
  browserLink,
  linkInstructions,
  onSave,
  onStartBrowserLink,
  onStartManualLink,
  onCaptureBrowserLink,
  onRefreshBrowserLink,
  onTest,
  onDisconnect
}: SourceSiteAuthRowProps) {
  const initialMode = site.authProfile.authMode === "none" ? site.supportedAuthModes[0] ?? "none" : site.authProfile.authMode;
  const [authMode, setAuthMode] = useState(initialMode);
  const [accountIdentifier, setAccountIdentifier] = useState(site.authProfile.accountIdentifier ?? "");
  const [label, setLabel] = useState(site.authProfile.label ?? "");
  const [headerName, setHeaderName] = useState(site.authProfile.headerName ?? "");
  const [secretValue, setSecretValue] = useState("");
  const [showManualSessionField, setShowManualSessionField] = useState(false);
  const requiresAccountIdentifier = authMode === "username_password" || authMode === "browser_session";
  const requiresSecret = ["api_token", "bearer_token", "cookie_header", "username_password"].includes(authMode);
  const canSaveManualBrowserSession =
    authMode === "browser_session" && showManualSessionField && accountIdentifier.trim().length > 0 && secretValue.trim().length > 0;
  const canSave =
    authMode === "none" ||
    (authMode === "browser_session"
      ? canSaveManualBrowserSession
      : (!requiresAccountIdentifier || accountIdentifier.trim().length > 0) &&
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
          icon={site.authProfile.authReady ? CheckCircle2 : AlertTriangle}
          label={sourceAuthStatusLabel(site.authProfile.linkStatus, authMode)}
          tone={site.authProfile.authReady ? "ok" : "warn"}
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
      {site.authProfile.linkStatusMessage ? <p className="muted-copy">{site.authProfile.linkStatusMessage}</p> : null}
      {linkInstructions ? (
        <div className="source-link-instructions">
          <p>{linkInstructions.storageNotes}</p>
          <ol>
            {linkInstructions.instructions.map((instruction) => (
              <li key={instruction}>{instruction}</li>
            ))}
          </ol>
        </div>
      ) : null}

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
        {authMode === "browser_session" && showManualSessionField ? (
          <label className="field-label">
            Printables session cookie/header
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
          {authMode === "browser_session" ? (
            <button
              className="text-button icon-action"
              disabled={isSaving || accountIdentifier.trim().length === 0}
              onClick={() =>
                onStartBrowserLink({
                  accountIdentifier: accountIdentifier.trim() || null,
                  label: label.trim() || null
                })
              }
              type="button"
            >
              {isSaving ? <Spinner size={15} /> : <Link2 size={15} aria-hidden="true" />}
              <span>Link with browser</span>
            </button>
          ) : null}
          {authMode === "browser_session" && browserLink ? (
            <>
              <button className="primary-action icon-action" disabled={isSaving} onClick={onCaptureBrowserLink} type="button">
                {isSaving ? <Spinner size={15} /> : <KeyRound size={15} aria-hidden="true" />}
                <span>Capture signed-in session</span>
              </button>
              <button className="text-button icon-action" disabled={isTesting} onClick={onRefreshBrowserLink} type="button">
                {isTesting ? <Spinner size={15} /> : <RefreshCw size={15} aria-hidden="true" />}
                <span>Refresh link status</span>
              </button>
            </>
          ) : null}
          {authMode === "browser_session" ? (
            <button
              className="text-button icon-action"
              disabled={isSaving}
              onClick={() => {
                setShowManualSessionField((current) => !current);
                if (!showManualSessionField) {
                  void onStartManualLink();
                }
              }}
              type="button"
            >
              <KeyRound size={15} aria-hidden="true" />
              <span>{showManualSessionField ? "Hide manual fallback" : "Manual fallback"}</span>
            </button>
          ) : null}
          {authMode !== "browser_session" || showManualSessionField ? (
            <button className="primary-action icon-action" type="submit" disabled={isSaving || !canSave}>
              {isSaving ? <Spinner size={15} /> : null}
              <span>{isSaving ? "Saving" : authMode === "browser_session" ? "Save session" : "Save"}</span>
            </button>
          ) : null}
          <button
            className="text-button icon-action"
            disabled={isTesting || authMode === "none"}
            onClick={onTest}
            type="button"
          >
            {isTesting ? <Spinner size={15} /> : <RefreshCw size={15} aria-hidden="true" />}
            <span>{isTesting ? "Testing" : "Test connection"}</span>
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
      {browserLink ? (
        <div className="browser-link-status" role="status">
          <StatusBadge
            icon={browserLink.status === "linked" ? CheckCircle2 : browserLink.status === "failed" ? AlertTriangle : RefreshCw}
            label={browserLinkStatusLabel(browserLink.status)}
            tone={browserLink.status === "linked" ? "ok" : browserLink.status === "failed" ? "warn" : "muted"}
          />
          <span>
            {browserLink.message}
            {browserLink.cookieCount > 0 ? ` Captured ${browserLink.cookieCount} site cookies.` : ""}
          </span>
        </div>
      ) : null}
    </article>
  );
}

function browserLinkStatusLabel(status: string) {
  const labels: Record<string, string> = {
    capture_requested: "Capturing",
    expired: "Expired",
    failed: "Capture failed",
    linked: "Session captured",
    running: "Waiting for login"
  };
  return labels[status] ?? "Browser link";
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

function sourceAuthStatusLabel(status: string, authMode: string) {
  const labels: Record<string, string> = {
    linked: "Linked",
    needs_relink: "Needs re-link",
    public_only: authMode === "browser_session" ? "Needs session" : "Public only",
    disabled: "Disabled",
    not_linked: "Not linked"
  };
  return labels[status] ?? "Not linked";
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
