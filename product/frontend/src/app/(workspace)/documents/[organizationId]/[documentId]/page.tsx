import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { DocumentDetail } from "@/components/document-detail";
import { getCurrentUser } from "@/lib/backend";
export const metadata: Metadata = { title: "Document review" };
export const dynamic = "force-dynamic";
export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ organizationId: string; documentId: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  const { organizationId, documentId } = await params;
  const organization = user.organizations.find(
    (item) => item.id === organizationId,
  );
  if (!organization) notFound();
  return (
    <DocumentDetail
      organizationId={organizationId}
      documentId={documentId}
      role={organization.role}
    />
  );
}
