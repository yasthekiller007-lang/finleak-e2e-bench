import type { ReactNode } from "react";

export function EmptyState({
  title,
  children,
  icon = "◇",
}: {
  title: string;
  children: ReactNode;
  icon?: string;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon" aria-hidden="true">
        {icon}
      </span>
      <h2>{title}</h2>
      <p className="muted">{children}</p>
    </div>
  );
}
