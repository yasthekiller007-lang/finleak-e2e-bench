import { proxySource } from "@/lib/source-proxy";
export async function GET(
  request: Request,
  context: { params: Promise<{ organizationId: string; documentId: string }> },
) {
  const { organizationId, documentId } = await context.params;
  return proxySource(request, organizationId, documentId, "source-status");
}
