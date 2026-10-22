// Operational correlation only. Never forward opaque arbitrary header values.
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function correlation(request?: Request): string {
  const supplied = request?.headers.get("X-Request-ID") ?? "";
  return uuid.test(supplied) ? supplied.toLowerCase() : crypto.randomUUID();
}
export function correlatedFailure(status: number, message: string) {
  const id = correlation();
  return Response.json(
    { error: { code: `http_${status}`, message, request_id: id } },
    { status, headers: { "Cache-Control": "no-store", "X-Request-ID": id } },
  );
}
export function copyCorrelation(from: Headers, to: Headers) {
  const id = from.get("X-Request-ID");
  if (id && uuid.test(id)) to.set("X-Request-ID", id.toLowerCase());
  const retry = from.get("Retry-After");
  if (retry && /^[0-9]{1,4}$/.test(retry) && Number(retry) <= 3600)
    to.set("Retry-After", retry);
}
