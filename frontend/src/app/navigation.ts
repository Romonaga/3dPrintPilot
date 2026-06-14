import { BarChart3, Bot, Cog, Cuboid, Gauge, Globe2, Printer, ScanSearch } from "lucide-react";

export type AppRouteId =
  | "dashboard"
  | "printers"
  | "models"
  | "siteScanning"
  | "compatibility"
  | "aiUsage"
  | "settings";

export type NavItem = {
  id: AppRouteId;
  label: string;
  icon: typeof Gauge;
};

export const navItems: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "printers", label: "Printers", icon: Printer },
  { id: "models", label: "Models", icon: Cuboid },
  { id: "siteScanning", label: "Site Scans", icon: Globe2 },
  { id: "compatibility", label: "Compatibility", icon: ScanSearch },
  { id: "aiUsage", label: "AI Usage", icon: Bot },
  { id: "settings", label: "Settings", icon: Cog }
];

export const dashboardQuickActions = [
  { label: "Scan LAN", icon: ScanSearch },
  { label: "Upload Model", icon: Cuboid },
  { label: "View Costs", icon: BarChart3 }
];
