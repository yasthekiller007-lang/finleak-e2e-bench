import { proxyRecovery } from "@/lib/recovery-proxy";
type Context = { params: Promise<{ organizationId: string; path: string[] }> };
export async function GET(request: Request, context: Context) {
  const { organizationId, path } = await context.params;
  return proxyRecovery(request, organizationId, path);
}
export async function POST(request: Request, context: Context) {
  const { organizationId, path } = await context.params;
  return proxyRecovery(request, organizationId, path);
}
