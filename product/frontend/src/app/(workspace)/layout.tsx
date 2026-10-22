import type { ReactNode } from "react";
import { Sidebar } from "@/components/sidebar";
import { getCurrentUser } from "@/lib/backend";
import { redirect } from "next/navigation";
import { SignOutButton } from "@/components/auth-buttons";

export const dynamic = "force-dynamic";

/** Every render verifies an API token and loads only this user's memberships. */
export default async function WorkspaceLayout({
  children,
}: {
  children: ReactNode;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return (
    <div className="workspace">
      <Sidebar />
      <div className="workspace-body">
        <header className="topbar">
          <span>
            Workspace <span className="breadcrumb-divider">/</span>{" "}
            Contract-to-Invoice
          </span>
          <span>
            {user.display_name} · <SignOutButton />
          </span>
        </header>
        <main id="main-content">{children}</main>
        <footer className="page-footer">
          Financial Leakage AI{" "}
          <span>Evidence first. Decisions with confidence.</span>
        </footer>
      </div>
    </div>
  );
}
