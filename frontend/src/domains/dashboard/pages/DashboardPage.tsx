import { QuickActions } from "../components/QuickActions";
import { PrinterInventory } from "../../printers/components/PrinterInventory";
import { CompatibilitySummary } from "../../compatibility/components/CompatibilitySummary";
import { AiCostSummary } from "../../ai-usage/components/AiCostSummary";
import { ResourceSummary } from "../../resources/components/ResourceSummary";
import { useDashboardSnapshot } from "../hooks/useDashboardSnapshot";
import { type AppRouteId } from "../../../app/navigation";

type DashboardPageProps = {
  onRouteChange: (route: AppRouteId) => void;
  onScanLan: () => void;
};

export default function DashboardPage({ onRouteChange, onScanLan }: DashboardPageProps) {
  const snapshot = useDashboardSnapshot();
  const openAiUsage = () => onRouteChange("aiUsage");

  return (
    <section className="dashboard-grid" aria-label="Dashboard">
      <QuickActions
        actions={snapshot.quickActions}
        onAction={(action) => {
          if (action === "Scan LAN") {
            onScanLan();
          }
          if (action === "Upload Model") {
            onRouteChange("models");
          }
          if (action === "View Costs") {
            openAiUsage();
          }
        }}
      />
      <PrinterInventory printers={snapshot.printers} onScanLan={onScanLan} />
      <CompatibilitySummary checks={snapshot.compatibilityChecks} />
      <AiCostSummary usage={snapshot.aiUsage} />
      <ResourceSummary resources={snapshot.resources} />
    </section>
  );
}
