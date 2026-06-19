import { lazy, Suspense, useState } from "react";
import { AppShell } from "../components/AppShell";
import { LoadingView } from "../components/LoadingView";
import { AuthPage } from "../domains/auth/pages/AuthPage";
import { useAuthSession } from "../domains/auth/hooks/useAuthSession";
import { useThemeMode } from "../hooks/useThemeMode";
import { navItems, type AppRouteId } from "./navigation";

const DashboardPage = lazy(() => import("../domains/dashboard/pages/DashboardPage"));
const AiUsagePage = lazy(() => import("../domains/ai-usage/pages/AiUsagePage"));
const CompatibilityPage = lazy(() => import("../domains/compatibility/pages/CompatibilityPage"));
const PrintersPage = lazy(() => import("../domains/printers/pages/PrintersPage"));
const SiteScanningPage = lazy(() => import("../domains/site-scanning/pages/SiteScanningPage"));
const SettingsPage = lazy(() => import("../domains/settings/pages/SettingsPage"));
const PlaceholderPage = lazy(() => import("../domains/system/pages/PlaceholderPage"));

const routeLabels: Record<AppRouteId, string> = Object.fromEntries(
  navItems.map((item) => [item.id, item.label])
) as Record<AppRouteId, string>;

export function App() {
  const [activeRoute, setActiveRoute] = useState<AppRouteId>("dashboard");
  const [printerScanRequestId, setPrinterScanRequestId] = useState<number | null>(null);
  const auth = useAuthSession();
  const themeMode = useThemeMode();
  const handleRouteChange = (route: AppRouteId) => {
    setActiveRoute(route);
    if (route !== "printers") {
      setPrinterScanRequestId(null);
    }
  };
  const handleDashboardScanLan = () => {
    setPrinterScanRequestId((current) => (current ?? 0) + 1);
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
        {activeRoute === "dashboard" ? <DashboardPage onRouteChange={setActiveRoute} onScanLan={handleDashboardScanLan} /> : null}
        {activeRoute === "aiUsage" ? <AiUsagePage /> : null}
        {activeRoute === "compatibility" ? <CompatibilityPage /> : null}
        {activeRoute === "printers" ? (
          <PrintersPage autoStartScanRequestId={printerScanRequestId} onAutoStartScanConsumed={() => setPrinterScanRequestId(null)} />
        ) : null}
        {activeRoute === "siteScanning" ? <SiteScanningPage /> : null}
        {activeRoute === "settings" ? <SettingsPage /> : null}
        {activeRoute !== "dashboard" &&
        activeRoute !== "aiUsage" &&
        activeRoute !== "compatibility" &&
        activeRoute !== "printers" &&
        activeRoute !== "siteScanning" &&
        activeRoute !== "settings" ? (
          <PlaceholderPage title={routeLabels[activeRoute]} />
        ) : null}
      </Suspense>
    </AppShell>
  );
}
