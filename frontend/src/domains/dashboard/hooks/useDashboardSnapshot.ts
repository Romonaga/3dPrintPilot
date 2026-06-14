import { useMemo } from "react";
import { dashboardQuickActions } from "../../../app/navigation";
import { type DashboardSnapshot } from "../types";

export function useDashboardSnapshot(): DashboardSnapshot {
  return useMemo(
    () => ({
      quickActions: dashboardQuickActions.map((action) => action.label),
      printers: [
        { id: "p1", name: "Voron 2.4", state: "Ready", buildVolume: "350 x 350 x 330", confidence: 98 },
        { id: "p2", name: "Prusa MK4", state: "Idle", buildVolume: "250 x 210 x 220", confidence: 91 },
        { id: "p3", name: "Bambu X1C", state: "Needs auth", buildVolume: "256 x 256 x 256", confidence: 67 }
      ],
      compatibilityChecks: [
        { id: "c1", model: "gearbox-housing.3mf", printer: "Voron 2.4", result: "Compatible", tone: "ok" },
        { id: "c2", model: "flex-hinge.stl", printer: "Prusa MK4", result: "Review TPU path", tone: "warn" },
        { id: "c3", model: "large-enclosure.stl", printer: "Bambu X1C", result: "Too tall", tone: "bad" }
      ],
      aiUsage: {
        ollamaRequests: 18,
        openAiFallbacks: 3,
        estimatedCost: "$0.0421",
        finalCost: "Pending",
        status: "Estimated"
      },
      resources: {
        gpuName: "RTX 3090",
        vram: "13%",
        queueDepth: 0,
        cpu: "32 threads"
      }
    }),
    []
  );
}

