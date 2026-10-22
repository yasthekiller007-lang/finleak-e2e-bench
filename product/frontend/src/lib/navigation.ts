export const productNavigation = [
  { href: "/dashboard", label: "Overview", icon: "overview" },
  { href: "/invoices", label: "Invoices", icon: "invoice" },
  { href: "/contracts", label: "Contracts", icon: "contract" },
  { href: "/anomalies", label: "Anomalies", icon: "anomaly" },
  { href: "/review", label: "Human review", icon: "review" },
] as const;

export const workspaceNavigation = [
  { href: "/dashboard", label: "Overview", symbol: "◫" },
  { href: "/documents", label: "Documents", symbol: "▤" },
  { href: "/leakage-cases", label: "Leakage cases", symbol: "◇" },
  { href: "/recovery-ledger", label: "Recovery ledger", symbol: "↺" },
  { href: "/settings", label: "Settings", symbol: "⚙" },
] as const;
