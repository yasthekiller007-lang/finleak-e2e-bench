import type { Metadata } from "next";
import { PageHeading } from "@/components/page-heading";
import { DocumentWorkspace } from "@/components/document-workspace";
import { getCurrentUser } from "@/lib/backend";
import { redirect } from "next/navigation";

export const metadata: Metadata = { title: "Documents" };
export const dynamic = "force-dynamic";

export default async function DocumentsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return (
    <>
      <PageHeading
        eyebrow="SOURCE MATERIAL"
        title="Documents"
        description="The starting point for every contract and invoice review."
      />
      <DocumentWorkspace user={user} />
    </>
  );
}
