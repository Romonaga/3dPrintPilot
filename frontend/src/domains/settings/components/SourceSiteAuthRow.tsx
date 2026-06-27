import { AlertTriangle, CheckCircle2, ExternalLink, Globe2, KeyRound, Link2, RefreshCw, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { StatusBadge } from "../../../components/StatusBadge";
import { type ModelSourceSiteStatus } from "../types";

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

export function SourceSiteAuthRow({
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
  const hasGuidedBrowserSetup = site.capabilities.includes("account_setup") && site.supportedAuthModes.includes("browser_session");
  const initialMode =
    site.authProfile.authMode === "none" && hasGuidedBrowserSetup
      ? "browser_session"
      : site.authProfile.authMode === "none"
        ? site.supportedAuthModes[0] ?? "none"
        : site.authProfile.authMode;
  const [authMode, setAuthMode] = useState(initialMode);
  const [accountIdentifier, setAccountIdentifier] = useState(site.authProfile.accountIdentifier ?? "");
  const [label, setLabel] = useState(site.authProfile.label ?? "");
  const [headerName, setHeaderName] = useState(site.authProfile.headerName ?? "");
  const [secretValue, setSecretValue] = useState("");
  const [showManualSessionField, setShowManualSessionField] = useState(false);
  const [showAdvancedSetup, setShowAdvancedSetup] = useState(false);
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

  async function handleGuidedBrowserStart(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onStartBrowserLink({
      accountIdentifier: accountIdentifier.trim() || null,
      label: label.trim() || null
    });
  }

  const statusAuthMode = hasGuidedBrowserSetup ? "browser_session" : authMode;
  const canStartGuidedBrowserLink = accountIdentifier.trim().length > 0;
  const hasManualFallback = site.supportedAuthModes.some((mode) => mode !== "none");
  const showManualForm = showAdvancedSetup && hasManualFallback;

  return (
    <article className="source-site-row">
      <div className="source-site-heading">
        <Globe2 size={18} aria-hidden="true" />
        <div>
          <h3>{site.displayName}</h3>
          <p>{site.baseUrl ?? site.allowedHosts.join(", ")}</p>
        </div>
      </div>

      <div className="source-site-badges" aria-label={`${site.displayName} source capabilities`}>
        <StatusBadge
          icon={site.authProfile.authReady ? CheckCircle2 : AlertTriangle}
          label={sourceAuthStatusLabel(site.authProfile.linkStatus, statusAuthMode)}
          tone={site.authProfile.authReady ? "ok" : "warn"}
        />
        <StatusBadge
          icon={site.supportLevel === "generic_only" ? AlertTriangle : CheckCircle2}
          label={supportLevelLabel(site.supportLevel)}
          tone={site.supportLevel === "generic_only" ? "warn" : site.supportLevel === "partial" ? "muted" : "ok"}
        />
        {site.capabilities.map((capability) => (
          <span className="capability-chip" key={capability}>
            {capabilityLabel(capability)}
          </span>
        ))}
      </div>

      <div className="secret-status">
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

      {hasGuidedBrowserSetup ? (
        <form className="source-site-form source-site-guided-form" onSubmit={handleGuidedBrowserStart}>
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
          <div className="source-site-actions">
            <button className="text-button icon-action" disabled={isSaving || !canStartGuidedBrowserLink} type="submit">
              {isSaving ? <Spinner size={15} /> : <Link2 size={15} aria-hidden="true" />}
              <span>Link with browser</span>
            </button>
            {browserLink ? (
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
            <button
              className="text-button icon-action"
              disabled={isTesting || site.authProfile.authMode === "none"}
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
      ) : (
        <div className="source-site-public-only">
          <StatusBadge icon={AlertTriangle} label="Public scan only" tone="warn" />
          <p>No supported runner is installed for managed login, download selection, or authenticated file import.</p>
        </div>
      )}

      {hasManualFallback ? (
        <button
          className="text-button icon-action source-site-advanced-toggle"
          type="button"
          onClick={() => setShowAdvancedSetup((current) => !current)}
        >
          <KeyRound size={15} aria-hidden="true" />
          <span>{showAdvancedSetup ? "Hide advanced fallback" : "Advanced fallback"}</span>
        </button>
      ) : null}

      {showManualForm ? (
        <form className="source-site-form source-site-manual-form" onSubmit={handleSubmit}>
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
          </div>
        </form>
      ) : null}
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

function supportLevelLabel(level: string) {
  const labels: Record<string, string> = {
    supported: "Supported site",
    partial: "Supported setup",
    generic_only: "Generic site",
    planned: "Planned"
  };
  return labels[level] ?? level;
}

function capabilityLabel(capability: string) {
  const labels: Record<string, string> = {
    public_scan: "Public scan",
    account_setup: "Account setup",
    project_lookup: "Project lookup",
    file_listing: "File listing",
    file_download: "File download",
    license_metadata: "License metadata"
  };
  return labels[capability] ?? capability;
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
