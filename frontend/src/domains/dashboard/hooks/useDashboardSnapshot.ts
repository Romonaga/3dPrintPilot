import { useEffect, useMemo, useState } from "react";
import { dashboardQuickActions } from "../../../app/navigation";
import { getAiAccountingStatus } from "../../ai-usage/api/aiUsageApi";
import { listCompatibilityChecks } from "../../compatibility/api/compatibilityApi";
import { type Printer } from "../../printers/types";
import { getResourceStatus } from "../../resources/api/resourcesApi";
import { type DashboardSnapshot } from "../types";

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
      printers.map((printer) => ({
        id: String(printer.id),
        name: printer.name,
        state: printer.state,
        buildVolume: formatBuildVolume(printer.buildVolumeXmm, printer.buildVolumeYmm, printer.buildVolumeZmm),
        confidence: printer.credentialConfigured ? 100 : 0
      })),
    [printers]
  );

  useEffect(() => {
    let isActive = true;

    async function loadDashboardData() {
      const [compatibilityResult, aiResult, resourceResult] = await Promise.allSettled([
        listCompatibilityChecks(),
        getAiAccountingStatus(),
        getResourceStatus()
      ]);

      if (!isActive) {
        return;
      }

      setSnapshot({
        quickActions: emptySnapshot.quickActions,
        printers: printerSummaries,
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
  }, [printerSummaries]);

  return {
    ...snapshot,
    printers: printerSummaries
  };
}

function formatBuildVolume(x: number | null, y: number | null, z: number | null) {
  if (x === null || y === null || z === null) {
    return "Build volume unknown";
  }
  return `${x} x ${y} x ${z} mm`;
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
