import { type LucideIcon } from "lucide-react";

type StatusBadgeProps = {
  icon: LucideIcon;
  label: string;
  tone: "ok" | "warn" | "muted";
};

export function StatusBadge({ icon: Icon, label, tone }: StatusBadgeProps) {
  return (
    <span className={`status-badge ${tone}`}>
      <Icon size={16} aria-hidden="true" />
      {label}
    </span>
  );
}

