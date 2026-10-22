import { proxyProof } from "@/lib/proof-proxy";
type Context = { params: Promise<{ organizationId: string; path: string[] }> };
export async function GET(request: Request, context: Context) {
  const { organizationId, path } = await context.params;
  return proxyProof(request, organizationId, path);
}
export async function POST(request: Request, context: Context) {
  const { organizationId, path } = await context.params;
  return proxyProof(request, organizationId, path);
}
