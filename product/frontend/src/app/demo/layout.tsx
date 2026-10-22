import Link from "next/link";
import type { ReactNode } from "react";
import { Sidebar } from "@/components/sidebar";

export default function DemoLayout({ children }: { children: ReactNode }) {
  return (
    <div className="workspace">
      <Sidebar />
      <div className="workspace-body">
        <header className="topbar">
          <span className="topbar-context">
            Workspace <span className="topbar-separator">/</span>{" "}
            Contract-to-Invoice
          </span>
          <div className="p-topbar-user">
            <span className="p-avatar">AM</span>
            <span>
              Alex Morgan<small>Synthetic demo user</small>
            </span>
            <Link href="/login">Sign in</Link>
          </div>
        </header>
        <main id="main-content">{children}</main>
        <footer className="page-footer">
          FINLEAK · Synthetic product exploration · No live financial results
        </footer>
      </div>
    </div>
  );
}
