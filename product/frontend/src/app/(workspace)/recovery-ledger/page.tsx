import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PageHeading } from "@/components/page-heading";
import { RecoveryWorkspace } from "@/components/recovery-workspace";
import { getCurrentUser } from "@/lib/backend";
export const metadata: Metadata = { title: "Recovery ledger" };
export const dynamic = "force-dynamic";
export default async function RecoveryLedgerPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return (
    <>
      <PageHeading
        eyebrow="INTERNAL PURSUIT & ECONOMIC EVIDENCE"
        title="Recovery ledger"
        description="Preserve reviewed recovery history without changing financial findings or proof."
      />
      <RecoveryWorkspace user={user} />
    </>
  );
}
