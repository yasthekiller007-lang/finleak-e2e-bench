import { proxyDocuments } from "@/lib/backend-proxy";

async function handle(
  request: Request,
  context: { params: Promise<{ organizationId: string }> },
) {
  const { organizationId } = await context.params;
  return proxyDocuments(request, organizationId);
}
export { handle as GET, handle as POST };
