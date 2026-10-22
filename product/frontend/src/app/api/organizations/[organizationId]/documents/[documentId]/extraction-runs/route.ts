import { proxyIntelligence } from "@/lib/intelligence-proxy";

export async function GET(
  request: Request,
  context: { params: Promise<{ organizationId: string; documentId: string }> },
) {
  const { organizationId, documentId } = await context.params;
  return proxyIntelligence(
    request,
    organizationId,
    documentId,
    "extraction-runs",
  );
}
