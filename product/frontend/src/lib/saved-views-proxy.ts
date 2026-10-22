import "server-only";
import { getBackendAccessToken } from "@/lib/auth-server";
import {
  correlation,
  correlatedFailure as fail,
  copyCorrelation,
} from "@/lib/proxy-correlation";
const uuid = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;
export async function proxySavedViews(
  request: Request,
  org: string,
  id?: string,
) {
  const token = await getBackendAccessToken();
  if (!token) return fail(401, "Sign in to continue.");
  if (!uuid.test(org) || (id !== undefined && !uuid.test(id)))
    return fail(404, "Personal view not found.");
  if (
    !(id ? ["GET", "PATCH", "DELETE"] : ["GET", "POST"]).includes(
      request.method,
    )
  )
    return fail(405, "Method not allowed.");
  const incoming = new URL(request.url);
  if (incoming.search.length > 2048)
    return fail(414, "Personal view query is too large.");
  const pairs = [...incoming.searchParams];
  if (
    pairs.some(
      ([k]) =>
        id !== undefined ||
        !["search", "view_type", "limit", "after"].includes(k),
    ) ||
    new Set(pairs.map(([k]) => k)).size !== pairs.length
  )
    return fail(422, "Invalid personal view query.");
  const backend = process.env.BACKEND_URL;
  if (!backend) return fail(503, "Personal views service is not configured.");
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
    "X-Request-ID": correlation(request),
  });
  let body: string | undefined;
  if (request.method !== "GET") {
    if (
      !process.env.NEXTAUTH_URL ||
      request.headers.get("origin") !== new URL(process.env.NEXTAUTH_URL).origin
    )
      return fail(403, "Request origin is not allowed.");
    if (!request.headers.get("content-type")?.startsWith("application/json"))
      return fail(415, "Use a JSON personal view request.");
    const reader = request.body?.getReader(),
      chunks: Uint8Array[] = [];
    let size = 0;
    if (reader) {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        size += chunk.value.byteLength;
        if (size > 16384) {
          await reader.cancel();
          return fail(413, "Personal view request is too large.");
        }
        chunks.push(chunk.value);
      }
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.length;
    }
    body = new TextDecoder().decode(bytes);
    headers.set("Content-Type", "application/json");
  }
  const url = new URL(
    `/api/v1/organizations/${org}/financial/saved-views${id ? `/${id}` : ""}`,
    backend,
  );
  url.search = incoming.search;
  try {
    const response = await fetch(url, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(30000)]),
    });
    const outgoing = new Headers({
      "Cache-Control": "no-store",
      "Content-Type": "application/json",
      "X-Content-Type-Options": "nosniff",
    });
    copyCorrelation(response.headers, outgoing);
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return fail(
      503,
      "Personal view response unavailable. The write outcome may be unknown. Reload your views before another write.",
    );
  }
}
