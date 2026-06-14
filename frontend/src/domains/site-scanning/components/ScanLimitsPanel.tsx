import { type SiteScanLimits } from "../types";

type ScanLimitsPanelProps = {
  limits: SiteScanLimits;
  onChange: (limits: SiteScanLimits) => void;
};

export function ScanLimitsPanel({ limits, onChange }: ScanLimitsPanelProps) {
  return (
    <section className="panel scan-limits-panel" aria-labelledby="scan-limits-title">
      <div className="panel-header">
        <h2 id="scan-limits-title">Limits</h2>
      </div>
      <div className="scan-limit-grid">
        <NumberField
          label="Depth"
          max={3}
          min={0}
          value={limits.maxDepth}
          onChange={(maxDepth) => onChange({ ...limits, maxDepth })}
        />
        <NumberField
          label="Pages"
          max={250}
          min={1}
          value={limits.maxPages}
          onChange={(maxPages) => onChange({ ...limits, maxPages })}
        />
        <NumberField
          label="Runtime"
          max={1800}
          min={30}
          value={limits.maxRuntimeSeconds}
          onChange={(maxRuntimeSeconds) => onChange({ ...limits, maxRuntimeSeconds })}
        />
        <NumberField
          label="Host slots"
          max={4}
          min={1}
          value={limits.perHostConcurrency}
          onChange={(perHostConcurrency) => onChange({ ...limits, perHostConcurrency })}
        />
      </div>
      <label className="toggle-row">
        <input
          type="checkbox"
          checked={limits.sameDomainOnly}
          onChange={(event) => onChange({ ...limits, sameDomainOnly: event.target.checked })}
        />
        <span>Same domain only</span>
      </label>
    </section>
  );
}

type NumberFieldProps = {
  label: string;
  max: number;
  min: number;
  onChange: (value: number) => void;
  value: number;
};

function NumberField({ label, max, min, onChange, value }: NumberFieldProps) {
  return (
    <label className="field-label">
      <span>{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
