import { AlertTriangle, CheckCircle2, Download, KeyRound, RefreshCw, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { StatusBadge } from "../../../components/StatusBadge";
import { downloadOperationsBackup } from "../../operations/api";
import { ResourceControlsPanel } from "../../resources/components/ResourceControlsPanel";
import { getFeatureSettings } from "../api/settingsApi";
import { useProviderSecrets } from "../hooks/useProviderSecrets";
import { type FeatureSettings, type ProviderSecretStatus } from "../types";

export default function SettingsPage() {
  const { secrets, isLoading, isSaving, error, reload, saveSecret, removeSecret } = useProviderSecrets();
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
