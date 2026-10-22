import { proxyIntelligence } from "@/lib/intelligence-proxy";

export async function POST(
  request: Request,
  context: { params: Promise<{ organizationId: string; documentId: string }> },
) {
  const { organizationId, documentId } = await context.params;
  return proxyIntelligence(request, organizationId, documentId, "process");
}
