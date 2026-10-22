import { proxyIntelligence } from "@/lib/intelligence-proxy";
export async function GET(
  request: Request,
  context: {
    params: Promise<{
      organizationId: string;
      documentId: string;
      runId: string;
    }>;
  },
) {
  const { organizationId, documentId, runId } = await context.params;
  return proxyIntelligence(
    request,
    organizationId,
    documentId,
    "extraction-runs",
    runId,
  );
}
