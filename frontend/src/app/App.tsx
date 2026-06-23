import { lazy, Suspense, useState } from "react";
import { AppShell } from "../components/AppShell";
import { LoadingView } from "../components/LoadingView";
import { AuthPage } from "../domains/auth/pages/AuthPage";
import { useAuthSession } from "../domains/auth/hooks/useAuthSession";
import { usePrinters } from "../domains/printers/hooks/usePrinters";
import { useThemeMode } from "../hooks/useThemeMode";
import { navItems, type AppRouteId } from "./navigation";

const DashboardPage = lazy(() => import("../domains/dashboard/pages/DashboardPage"));
const AiUsagePage = lazy(() => import("../domains/ai-usage/pages/AiUsagePage"));
const CompatibilityPage = lazy(() => import("../domains/compatibility/pages/CompatibilityPage"));
const ModelsPage = lazy(() => import("../domains/models/pages/ModelsPage"));
const PrintersPage = lazy(() => import("../domains/printers/pages/PrintersPage"));
const SiteScanningPage = lazy(() => import("../domains/site-scanning/pages/SiteScanningPage"));
const SettingsPage = lazy(() => import("../domains/settings/pages/SettingsPage"));

const routeLabels: Record<AppRouteId, string> = Object.fromEntries(
  navItems.map((item) => [item.id, item.label])
) as Record<AppRouteId, string>;

export function App() {
  const [activeRoute, setActiveRoute] = useState<AppRouteId>("dashboard");
  const [visitedRoutes, setVisitedRoutes] = useState<Set<AppRouteId>>(() => new Set(["dashboard"]));
  const [printerScanRequestId, setPrinterScanRequestId] = useState<number | null>(null);
  const auth = useAuthSession();
  const themeMode = useThemeMode();
  const isAppSessionReady =
    !auth.isLoading && !auth.bootstrapRequired && auth.user !== null && !auth.user.forcePasswordChange;
  const printers = usePrinters({ enabled: isAppSessionReady });
  const isRouteVisited = (route: AppRouteId) => visitedRoutes.has(route);
  const markRouteVisited = (route: AppRouteId) => {
    setVisitedRoutes((current) => {
      if (current.has(route)) {
        return current;
      }
      const next = new Set(current);
      next.add(route);
      return next;
    });
  };
  const handleRouteChange = (route: AppRouteId) => {
    markRouteVisited(route);
    setActiveRoute(route);
    if (route !== "printers") {
      setPrinterScanRequestId(null);
    }
  };
  const handleDashboardScanLan = () => {
    setPrinterScanRequestId((current) => (current ?? 0) + 1);
    markRouteVisited("printers");
    setActiveRoute("printers");
  };

  if (auth.isLoading) {
    return <LoadingView label="Session" />;
  }

  if (auth.bootstrapRequired || auth.user === null) {
    return (
      <AuthPage
        mode={auth.bootstrapRequired ? "bootstrap" : "login"}
        error={auth.error}
        onBootstrap={auth.bootstrap}
        onLogin={auth.signIn}
        onChangePassword={auth.updatePassword}
      />
    );
  }

  if (auth.user.forcePasswordChange) {
    return (
      <AuthPage
        mode="change-password"
        error={auth.error}
        onBootstrap={auth.bootstrap}
        onLogin={auth.signIn}
        onChangePassword={auth.updatePassword}
      />
    );
  }

  return (
    <AppShell
      activeRoute={activeRoute}
      isDarkMode={themeMode.isDark}
      navItems={navItems}
      user={auth.user}
      onLogout={auth.signOut}
      onRouteChange={handleRouteChange}
      onThemeToggle={themeMode.toggleTheme}
    >
      <Suspense fallback={<LoadingView label={routeLabels[activeRoute]} />}>
        {isRouteVisited("dashboard") ? (
          <div hidden={activeRoute !== "dashboard"}>
            <DashboardPage
              printers={printers.printers}
              onRouteChange={handleRouteChange}
              onScanLan={handleDashboardScanLan}
            />
          </div>
        ) : null}
        {isRouteVisited("aiUsage") ? (
          <div hidden={activeRoute !== "aiUsage"}>
            <AiUsagePage />
          </div>
        ) : null}
        {isRouteVisited("compatibility") ? (
          <div hidden={activeRoute !== "compatibility"}>
            <CompatibilityPage />
          </div>
        ) : null}
        {isRouteVisited("models") ? (
          <div hidden={activeRoute !== "models"}>
            <ModelsPage />
          </div>
        ) : null}
        {isRouteVisited("printers") ? (
          <div hidden={activeRoute !== "printers"}>
            <PrintersPage
              autoStartScanRequestId={printerScanRequestId}
              printers={printers}
              onAutoStartScanConsumed={() => setPrinterScanRequestId(null)}
            />
          </div>
        ) : null}
        {isRouteVisited("siteScanning") ? (
          <div hidden={activeRoute !== "siteScanning"}>
            <SiteScanningPage />
          </div>
        ) : null}
        {isRouteVisited("settings") ? (
          <div hidden={activeRoute !== "settings"}>
            <SettingsPage user={auth.user} />
          </div>
        ) : null}
      </Suspense>
    </AppShell>
  );
}
