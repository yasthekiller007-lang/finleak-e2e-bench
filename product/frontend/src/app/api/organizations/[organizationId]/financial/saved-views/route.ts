import { proxySavedViews } from "@/lib/saved-views-proxy";
type Context = { params: Promise<{ organizationId: string }> };
export async function GET(request: Request, context: Context) {
  return proxySavedViews(request, (await context.params).organizationId);
}
export async function POST(request: Request, context: Context) {
  return proxySavedViews(request, (await context.params).organizationId);
}
