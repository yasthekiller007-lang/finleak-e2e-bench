import { proxyDocuments } from "@/lib/backend-proxy";

export async function GET(
  request: Request,
  context: { params: Promise<{ organizationId: string; documentId: string }> },
) {
  const { organizationId, documentId } = await context.params;
  return proxyDocuments(request, organizationId, documentId, true);
}
