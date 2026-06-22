import { useEffect, useMemo, useState } from "react";
import { dashboardQuickActions } from "../../../app/navigation";
import { getAiAccountingStatus } from "../../ai-usage/api/aiUsageApi";
import { listCompatibilityChecks } from "../../compatibility/api/compatibilityApi";
import { getPrinterJobStatus } from "../../printers/api/printersApi";
import { type Printer, type PrinterJobStatus } from "../../printers/types";
import { getResourceStatus } from "../../resources/api/resourcesApi";
import { type DashboardSnapshot, type PrinterSummary } from "../types";

type UseDashboardSnapshotOptions = {
  printers: Printer[];
};

const emptySnapshot: DashboardSnapshot = {
  quickActions: dashboardQuickActions.map((action) => action.label),
  printers: [],
  compatibilityChecks: [],
  aiUsage: {
    localModel: "Unavailable",
    fallbackStatus: "Unknown",
    estimatedMonthToDate: "$0.00",
    budgetRemaining: "Unknown",
    status: "Unavailable"
  },
  resources: {
    gpuName: "Unavailable",
    vram: "Unknown",
    queueDepth: 0,
    cpu: "Unknown",
    status: "Unavailable"
  }
};

export function useDashboardSnapshot({ printers }: UseDashboardSnapshotOptions): DashboardSnapshot {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot>(emptySnapshot);

  const printerSummaries = useMemo(
    () =>
      printers.map((printer) => printerSummaryFromRecord(printer)),
    [printers]
  );

  useEffect(() => {
    let isActive = true;

    async function loadDashboardData() {
      const [compatibilityResult, aiResult, resourceResult, printerStatusResult] = await Promise.allSettled([
        listCompatibilityChecks(),
        getAiAccountingStatus(),
        getResourceStatus(),
        loadPrinterJobStatuses(printers)
      ]);

      if (!isActive) {
        return;
      }

      const jobStatusByPrinterId =
        printerStatusResult.status === "fulfilled" ? printerStatusResult.value : new Map<number, PrinterJobStatus>();

      setSnapshot({
        quickActions: emptySnapshot.quickActions,
        printers: printers.map((printer) => printerSummaryFromRecord(printer, jobStatusByPrinterId.get(printer.id))),
        compatibilityChecks:
          compatibilityResult.status === "fulfilled"
            ? compatibilityResult.value.slice(0, 3).map((check) => ({
                id: String(check.id),
                model: check.modelTitle,
                printer: check.printerName,
                result: compatibilityLabel(check.status),
                tone: compatibilityTone(check.status)
              }))
            : [],
        aiUsage:
          aiResult.status === "fulfilled"
            ? {
                localModel: aiResult.value.localModel,
                fallbackStatus: aiResult.value.openAiFallbackEnabled ? "Enabled" : "Disabled",
                estimatedMonthToDate: formatUsd(aiResult.value.estimatedMonthToDateUsd),
                budgetRemaining: formatUsd(aiResult.value.budgetRemainingUsd),
                status: aiResult.value.reconciliationRequired ? "Estimated" : "Current"
              }
            : emptySnapshot.aiUsage,
        resources:
          resourceResult.status === "fulfilled"
            ? {
                gpuName: resourceResult.value.gpu.available ? resourceResult.value.gpu.name ?? "GPU detected" : "Unavailable",
                vram:
                  resourceResult.value.gpu.memoryUsedPercent !== null
                    ? `${resourceResult.value.gpu.memoryUsedPercent}%`
                    : "Unknown",
                queueDepth: resourceResult.value.queues.local_llm?.pendingCount ?? 0,
                cpu: `${resourceResult.value.cpu.cores} threads`,
                status: resourceResult.value.gpu.available ? "Live" : "No GPU"
              }
            : emptySnapshot.resources
      });
    }

    void loadDashboardData();
    return () => {
      isActive = false;
    };
  }, [printers, printerSummaries]);

  const snapshotPrinterIds = snapshot.printers.map((printer) => printer.id).join("|");
  const currentPrinterIds = printerSummaries.map((printer) => printer.id).join("|");
  return {
    ...snapshot,
    printers: snapshotPrinterIds === currentPrinterIds ? snapshot.printers : printerSummaries
  };
}

async function loadPrinterJobStatuses(printers: Printer[]) {
  const supportedPrinters = printers.filter(supportsDashboardJobStatus);
  const statusResults = await Promise.allSettled(
    supportedPrinters.map(async (printer) => [printer.id, await getPrinterJobStatus(printer.id)] as const)
  );
  const statusByPrinterId = new Map<number, PrinterJobStatus>();
  statusResults.forEach((result) => {
    if (result.status === "fulfilled") {
      statusByPrinterId.set(result.value[0], result.value[1]);
    }
  });
  return statusByPrinterId;
}

function printerSummaryFromRecord(printer: Printer, jobStatus?: PrinterJobStatus): PrinterSummary {
  const progressPercent = activeProgressPercent(jobStatus);
  return {
    id: String(printer.id),
    name: printer.name,
    buildVolume: formatBuildVolume(printer.buildVolumeXmm, printer.buildVolumeYmm, printer.buildVolumeZmm),
    availabilityLabel: formatAvailabilityLabel(printer.state),
    availabilityTone: availabilityTone(printer.state),
    jobStatusLabel: formatJobStatusLabel(printer, jobStatus),
    progressPercent,
    progressLabel: progressPercent === null ? null : `${progressPercent}%`
  };
}

function supportsDashboardJobStatus(printer: Printer) {
  const capabilities = printer.capabilities ?? {};
  const capabilityAdapter = typeof capabilities.adapter === "string" ? capabilities.adapter : "";
  const haystack = `${printer.adapterType ?? ""} ${printer.printerType} ${capabilityAdapter}`.toLowerCase();
  return ["moonraker", "klipper", "snapmaker", "creality"].some((marker) => haystack.includes(marker));
}

function formatAvailabilityLabel(state: string | null | undefined) {
  const normalized = (state ?? "").trim().toLowerCase();
  if (normalized === "online") {
    return "Online";
  }
  if (normalized === "offline") {
    return "Offline";
  }
  if (normalized === "confirmed") {
    return "Confirmed";
  }
  if (normalized === "manual") {
    return "Manual";
  }
  if (normalized === "error") {
    return "Error";
  }
  if (normalized === "") {
    return "Unknown";
  }
  return titleCase(normalized.replace(/[_-]+/g, " "));
}

function availabilityTone(state: string | null | undefined): PrinterSummary["availabilityTone"] {
  const normalized = (state ?? "").trim().toLowerCase();
  if (normalized === "online" || normalized === "confirmed") {
    return "ok";
  }
  if (normalized === "manual" || normalized === "unknown" || normalized === "") {
    return "neutral";
  }
  if (normalized === "offline" || normalized === "unsupported") {
    return "warn";
  }
  return "bad";
}

function formatJobStatusLabel(printer: Printer, jobStatus?: PrinterJobStatus) {
  if (!supportsDashboardJobStatus(printer)) {
    return "Print telemetry unavailable";
  }
  if (!jobStatus) {
    return "Print status unknown";
  }
  const state = formatJobState(jobStatus.state);
  return jobStatus.filename ? `${state} - ${jobStatus.filename}` : state;
}

function formatJobState(state: string | null | undefined) {
  const normalized = (state ?? "").trim().toLowerCase();
  if (normalized === "printing") {
    return "Printing";
  }
  if (normalized === "paused" || normalized === "pause") {
    return "Paused";
  }
  if (["standby", "ready", "complete", "completed", "idle"].includes(normalized)) {
    return "Idle";
  }
  if (normalized === "error") {
    return "Error";
  }
  if (normalized === "") {
    return "State unknown";
  }
  return titleCase(normalized.replace(/[_-]+/g, " "));
}

function activeProgressPercent(jobStatus?: PrinterJobStatus) {
  if (!jobStatus || !["printing", "paused", "pause"].includes((jobStatus.state ?? "").trim().toLowerCase())) {
    return null;
  }
  const progress = jobStatus.progress;
  if (typeof progress !== "number" || !Number.isFinite(progress)) {
    return null;
  }
  const normalized = progress <= 1 ? progress * 100 : progress;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function formatBuildVolume(x: number | null, y: number | null, z: number | null) {
  if (x === null || y === null || z === null) {
    return "Build volume unknown";
  }
  return `${x} x ${y} x ${z} mm`;
}

function titleCase(value: string) {
  return value.replace(/\b\w/g, (character) => character.toUpperCase());
}

function compatibilityTone(status: "pass" | "warning" | "fail") {
  if (status === "pass") {
    return "ok";
  }
  if (status === "warning") {
    return "warn";
  }
  return "bad";
}

function compatibilityLabel(status: "pass" | "warning" | "fail") {
  if (status === "pass") {
    return "Compatible";
  }
  if (status === "warning") {
    return "Review needed";
  }
  return "Blocked";
}

function formatUsd(value: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return "Unknown";
  }
  return `$${amount.toFixed(2)}`;
}
