"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { productNavigation, workspaceNavigation } from "@/lib/navigation";
import { ProductIcon } from "@/components/product-icons";

export function Sidebar() {
  const pathname = usePathname();
  const demo = pathname.startsWith("/demo/");
  const prefix = demo ? "/demo" : "";
  return (
    <aside className="sidebar">
      <Link
        className="brand"
        href={`${prefix}/dashboard`}
        aria-label="Financial Leakage AI overview"
      >
        <span className="brand-mark" aria-hidden="true">
          F
        </span>
        <span>
          FINLEAK<span className="brand-caption">Financial intelligence</span>
        </span>
      </Link>
      <p className="nav-label">WORKSPACE</p>
      <nav aria-label="Workspace navigation">
        {productNavigation.map((item) => (
          <Link
            key={item.href}
            href={`${prefix}${item.href}`}
            className={`nav-link${pathname === `${prefix}${item.href}` ? " active" : ""}`}
            aria-current={
              pathname === `${prefix}${item.href}` ? "page" : undefined
            }
          >
            <ProductIcon name={item.icon} size={19} />
            {item.label}
          </Link>
        ))}
      </nav>
      {!demo && (
        <>
          <p className="nav-label">SOURCE & GOVERNANCE</p>
          <nav aria-label="Source and governance navigation">
            {workspaceNavigation
              .filter((item) => item.href !== "/dashboard")
              .map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-link${pathname.startsWith(item.href) ? " active" : ""}`}
                  aria-current={
                    pathname.startsWith(item.href) ? "page" : undefined
                  }
                >
                  <span aria-hidden="true">{item.symbol}</span>
                  {item.label}
                </Link>
              ))}
          </nav>
        </>
      )}
      <div className="sidebar-footer">
        <span className="status-dot" aria-hidden="true" />
        <span>
          {demo ? "Synthetic workspace" : "Human-led decisions"}
          <span className="brand-caption">
            {demo ? "No live connections" : "Evidence-led financial review"}
          </span>
        </span>
      </div>
    </aside>
  );
}
