import { type ReactNode } from "react";
import { Cpu, LogOut, Moon, Network, ShieldCheck, Sun, UserRound } from "lucide-react";
import { type AppRouteId, type NavItem } from "../app/navigation";
import { type AuthUser } from "../domains/auth/types";
import { Sidebar } from "./Sidebar";
import { StatusBadge } from "./StatusBadge";

type AppShellProps = {
  activeRoute: AppRouteId;
  isDarkMode: boolean;
  navItems: NavItem[];
  user: AuthUser;
  onLogout: () => void;
  onRouteChange: (route: AppRouteId) => void;
  onThemeToggle: () => void;
  children: ReactNode;
};

export function AppShell({
  activeRoute,
  isDarkMode,
  navItems,
  user,
  onLogout,
  onRouteChange,
  onThemeToggle,
  children
}: AppShellProps) {
  const ThemeIcon = isDarkMode ? Sun : Moon;

  return (
    <div className="app-shell">
      <Sidebar activeRoute={activeRoute} navItems={navItems} onRouteChange={onRouteChange} />
      <main className="app-main">
        <header className="topbar">
          <div>
            <p className="eyeline">Local server</p>
            <h1>3D Print Pilot</h1>
          </div>
          <div className="topbar-status">
            <StatusBadge icon={Network} label="LAN Ready" tone="ok" />
            <StatusBadge icon={Cpu} label="GPU Queue" tone="warn" />
            <StatusBadge icon={ShieldCheck} label="Cost Verified" tone="muted" />
            <StatusBadge icon={UserRound} label={`${user.username} / ${user.role}`} tone="muted" />
            <button
              aria-label={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
              className="theme-toggle"
              type="button"
              onClick={onThemeToggle}
            >
              <ThemeIcon size={16} aria-hidden="true" />
              <span>{isDarkMode ? "Light" : "Dark"}</span>
            </button>
            <button aria-label="Sign out" className="icon-only-button" onClick={onLogout} title="Sign out" type="button">
              <LogOut size={16} aria-hidden="true" />
            </button>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
