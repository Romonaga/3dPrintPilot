import { type PrinterRefreshInfo } from "../hooks/usePrinters";

export function formatEndpoint(protocol: string, host: string, port: number) {
  return `${protocol}://${host}:${port}`;
}

export function BambuLanNotice({ variant }: { variant: "saved" | "discovered" }) {
  const prefix = variant === "saved" ? "Bambu LAN" : "Bambu discovery";
  return (
    <p className="muted-copy">
      {prefix}: scan-only visibility works without credentials. Full local MQTT telemetry needs the printer LAN access code
      and LAN or Developer mode, which may limit Bambu Handy or cloud workflows on some firmware.
    </p>
  );
}

export function PrinterRefreshSummary({ refreshInfo }: { refreshInfo: PrinterRefreshInfo }) {
  const jobLabel = formatJobLabel(refreshInfo);
  const filamentLabels = formatFilamentLabels(refreshInfo);
  const bambuLabels = formatBambuStatusLabels(refreshInfo);
  const diagnosticLabel = formatDiagnosticLabel(refreshInfo);
  return (
    <div className="printer-refresh-summary" aria-label="Refreshed printer info">
      <span>State: {refreshInfo.status.state}</span>
      {jobLabel ? <span>{jobLabel}</span> : null}
      {filamentLabels.map((label) => (
        <span key={label}>{label}</span>
      ))}
      {bambuLabels.map((label) => (
        <span key={label}>{label}</span>
      ))}
      {diagnosticLabel ? <span>{diagnosticLabel}</span> : null}
    </div>
  );
}

function formatJobLabel(refreshInfo: PrinterRefreshInfo) {
  const jobStatus = refreshInfo.jobStatus;
  if (!jobStatus) {
    return null;
  }
  const progress = formatProgressPercent(jobStatus.progress);
  const filename = jobStatus.filename ? ` - ${jobStatus.filename}` : "";
  return progress === null ? `Job: ${jobStatus.state}${filename}` : `Job: ${jobStatus.state}${filename} (${progress}%)`;
}

function formatFilamentLabels(refreshInfo: PrinterRefreshInfo) {
  return (refreshInfo.jobStatus?.toolheads ?? [])
    .map((toolhead) => {
      const material = [toolhead.material, toolhead.vendor, toolhead.subtype].filter(Boolean).join(" / ");
      if (material && toolhead.color) {
        return `${toolhead.label}: ${material} ${toolhead.color}`;
      }
      if (material) {
        return `${toolhead.label}: ${material}`;
      }
      if (toolhead.color) {
        return `${toolhead.label}: ${toolhead.color}`;
      }
      return null;
    })
    .filter((label): label is string => label !== null);
}

function formatDiagnosticLabel(refreshInfo: PrinterRefreshInfo) {
  const diagnostics = refreshInfo.capabilityDiagnostics;
  if (!diagnostics) {
    return null;
  }
  const agentCount = diagnostics.extensionAgents.length;
  const spoolman = diagnostics.spoolmanAvailable ? "Spoolman available" : "Spoolman unavailable";
  return `${agentCount} extension agents / ${spoolman}`;
}

function formatBambuStatusLabels(refreshInfo: PrinterRefreshInfo) {
  if (refreshInfo.status.adapterType !== "bambu_mqtt") {
    return [];
  }
  const rawStatus = refreshInfo.status.rawStatus;
  const labels: string[] = [];
  const message = stringField(rawStatus, "message");
  const job = recordField(rawStatus, "job");
  const temperatures = recordField(rawStatus, "temperatures");
  const ams = recordField(rawStatus, "ams");
  if (job) {
    const jobState = stringField(job, "state");
    const filename = stringField(job, "filename");
    const progress = formatProgressPercent(numberField(job, "progress"));
    if (jobState) {
      labels.push(progress === null ? `Job: ${jobState}${filename ? ` - ${filename}` : ""}` : `Job: ${jobState} (${progress}%)`);
    }
  }
  const tempLabel = formatBambuTemperatureLabel(temperatures);
  if (tempLabel) {
    labels.push(tempLabel);
  }
  labels.push(...formatBambuAmsLabels(ams));
  if (message && labels.length === 0) {
    labels.push(message);
  }
  return labels;
}

function formatBambuTemperatureLabel(temperatures: Record<string, unknown> | null) {
  if (!temperatures) {
    return null;
  }
  const nozzle = formatTemperaturePair(
    numberField(temperatures, "nozzle_current_c"),
    numberField(temperatures, "nozzle_target_c")
  );
  const bed = formatTemperaturePair(numberField(temperatures, "bed_current_c"), numberField(temperatures, "bed_target_c"));
  return [nozzle ? `Nozzle ${nozzle}` : null, bed ? `Bed ${bed}` : null].filter(Boolean).join(" / ") || null;
}

function formatBambuAmsLabels(ams: Record<string, unknown> | null) {
  if (!ams) {
    return [];
  }
  const activeTray = stringField(ams, "active_tray");
  const trays = Array.isArray(ams.trays) ? ams.trays : [];
  return trays
    .map((tray) => (isRecord(tray) ? formatBambuTrayLabel(tray, activeTray) : null))
    .filter((label): label is string => label !== null);
}

function formatBambuTrayLabel(tray: Record<string, unknown>, activeTray: string | null) {
  const id = stringField(tray, "id");
  const color = stringField(tray, "color");
  const material = [stringField(tray, "material"), stringField(tray, "subtype")].filter(Boolean).join(" / ");
  const active = Boolean(tray.active) || (id !== null && id === activeTray);
  const prefix = active ? `AMS T${id ?? "?"} active` : `AMS T${id ?? "?"}`;
  if (material && color) {
    return `${prefix}: ${material} ${color}`;
  }
  if (material) {
    return `${prefix}: ${material}`;
  }
  return color ? `${prefix}: ${color}` : null;
}

function formatTemperaturePair(current: number | null, target: number | null) {
  if (current === null && target === null) {
    return null;
  }
  const currentLabel = current === null ? "?" : `${Math.round(current)}C`;
  return target === null || target === 0 ? currentLabel : `${currentLabel}/${Math.round(target)}C`;
}

function formatProgressPercent(progress: number | null | undefined) {
  if (typeof progress !== "number" || !Number.isFinite(progress)) {
    return null;
  }
  const normalized = progress <= 1 ? progress * 100 : progress;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function recordField(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return isRecord(value) ? value : null;
}

function stringField(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function numberField(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function formatPorts(ports: number[]) {
  if (ports.length === 0) {
    return "unknown";
  }
  return ports.join(", ");
}

export function formatBuildVolume(x: number | null, y: number | null, z: number | null) {
  if (!x || !y || !z) {
    return "Build volume unknown";
  }
  return `${x} x ${y} x ${z} mm`;
}

export function isBambuLanPrinter(printer: { printerType?: string; serviceType?: string; protocol: string; capabilities?: Record<string, unknown> }) {
  const adapter = typeof printer.capabilities?.adapter === "string" ? printer.capabilities.adapter : "";
  const source = `${printer.printerType ?? ""} ${printer.serviceType ?? ""} ${printer.protocol} ${adapter}`.toLowerCase();
  return source.includes("bambu") || source.includes("mqtt_probe:bambu_mqtt");
}
