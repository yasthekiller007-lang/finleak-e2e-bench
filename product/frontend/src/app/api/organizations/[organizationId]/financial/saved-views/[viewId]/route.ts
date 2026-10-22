import { proxySavedViews } from "@/lib/saved-views-proxy";
type Context = { params: Promise<{ organizationId: string; viewId: string }> };
export async function GET(request: Request, context: Context) {
  const p = await context.params;
  return proxySavedViews(request, p.organizationId, p.viewId);
}
export async function PATCH(request: Request, context: Context) {
  const p = await context.params;
  return proxySavedViews(request, p.organizationId, p.viewId);
}
export async function DELETE(request: Request, context: Context) {
  const p = await context.params;
  return proxySavedViews(request, p.organizationId, p.viewId);
}
