import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PageHeading } from "@/components/page-heading";
import { FinancialWorkspace } from "@/components/financial-workspace";
import { getCurrentUser } from "@/lib/backend";
export const metadata: Metadata = { title: "Leakage cases" };
export const dynamic = "force-dynamic";
export default async function LeakageCasesPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return (
    <>
      <PageHeading
        eyebrow="EVIDENCE & REVIEW"
        title="Leakage cases"
        description="Review supported contractual discrepancies and the evidence needed to assess blocked scopes."
      />
      <FinancialWorkspace user={user} />
    </>
  );
}
