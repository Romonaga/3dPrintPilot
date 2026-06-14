import { type AppRouteId, type NavItem } from "../app/navigation";

type SidebarProps = {
  activeRoute: AppRouteId;
  navItems: NavItem[];
  onRouteChange: (route: AppRouteId) => void;
};

export function Sidebar({ activeRoute, navItems, onRouteChange }: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand-lockup">
        <span className="brand-mark">3P</span>
        <span>3D Print Pilot</span>
      </div>
      <nav className="nav-list">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={item.id === activeRoute ? "nav-item active" : "nav-item"}
              type="button"
              onClick={() => onRouteChange(item.id)}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
