import { QuickActions } from "../components/QuickActions";
import { PrinterInventory } from "../components/PrinterInventory";
import { CompatibilitySummary } from "../../compatibility/components/CompatibilitySummary";
import { AiCostSummary } from "../../ai-usage/components/AiCostSummary";
import { ResourceSummary } from "../../resources/components/ResourceSummary";
import { SupportedSourceImportPanel } from "../../source-sites/components/SupportedSourceImportPanel";
import { useDashboardSnapshot } from "../hooks/useDashboardSnapshot";
import { type AppRouteId } from "../../../app/navigation";
import { type Printer } from "../../printers/types";

type DashboardPageProps = {
  onRouteChange: (route: AppRouteId) => void;
  onScanLan: () => void;
  printers: Printer[];
};

export default function DashboardPage({ onRouteChange, onScanLan, printers }: DashboardPageProps) {
  const snapshot = useDashboardSnapshot({ printers });
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
      <SupportedSourceImportPanel
        className="panel dashboard-source-panel"
        heading="Find Models"
        headingId="dashboard-source-import-title"
        showImportedSummary
      />
      <PrinterInventory printers={snapshot.printers} printerRecords={printers} onScanLan={onScanLan} />
      <CompatibilitySummary checks={snapshot.compatibilityChecks} />
      <AiCostSummary usage={snapshot.aiUsage} />
      <ResourceSummary resources={snapshot.resources} />
    </section>
  );
}
