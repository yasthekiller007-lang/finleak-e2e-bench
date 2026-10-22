import { proxyFinancial } from "@/lib/financial-proxy";

type Context = { params: Promise<{ organizationId: string; path: string[] }> };
export async function GET(request: Request, context: Context) {
  const { organizationId, path } = await context.params;
  return proxyFinancial(request, organizationId, path);
}
export async function POST(request: Request, context: Context) {
  const { organizationId, path } = await context.params;
  return proxyFinancial(request, organizationId, path);
}
