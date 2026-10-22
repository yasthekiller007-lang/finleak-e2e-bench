import { proxySource } from "@/lib/source-proxy";
export async function POST(
  request: Request,
  context: { params: Promise<{ organizationId: string; documentId: string }> },
) {
  const { organizationId, documentId } = await context.params;
  return proxySource(request, organizationId, documentId, "scan");
}
