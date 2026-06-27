import { AlertTriangle, CheckCircle2, KeyRound, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import { Spinner } from "../../../components/Spinner";
import { StatusBadge } from "../../../components/StatusBadge";
import { type ProviderSecretStatus } from "../types";

type SecretRowProps = {
  secret: ProviderSecretStatus;
  isSaving: boolean;
  onSave: (value: string) => Promise<void>;
  onRemove: () => Promise<void>;
};

export function SecretRow({ secret, isSaving, onSave, onRemove }: SecretRowProps) {
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
