import "server-only";
import { getBackendAccessToken } from "@/lib/auth-server";
import {
  correlation,
  correlatedFailure,
  copyCorrelation,
} from "@/lib/proxy-correlation";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const fail = correlatedFailure;
export async function proxyFinancial(
  request: Request,
  organizationId: string,
  path: string[],
) {
  const token = await getBackendAccessToken();
  if (!token) return fail(401, "Sign in to continue.");
  if (!uuid.test(organizationId)) return fail(404, "Resource not found.");
  const route = path.join("/");
  const id = "[0-9a-f-]{36}";
  const read =
    /^(sources|evaluations|exception-facets|summary|audit)$/.test(route) ||
    new RegExp(`^(sources|evaluations)/${id}$`, "i").test(route) ||
    new RegExp(`^sources/${id}/(history|compile)$`, "i").test(route);
  const write =
    route === "sources" ||
    new RegExp(`^sources/${id}/(reviews|evaluate)$`, "i").test(route) ||
    new RegExp(`^evaluations/${id}/decision$`, "i").test(route);
  if (
    path.some((p) => p.includes("..")) ||
    (path.length > 1 && !uuid.test(path[1]))
  )
    return fail(404, "Resource not found.");
  if (
    !(request.method === "GET" && read) &&
    !(request.method === "POST" && write)
  )
    return fail(405, "Method not allowed.");
  const backend = process.env.BACKEND_URL;
  if (!backend) return fail(503, "Financial review service is not configured.");
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
    "X-Request-ID": correlation(request),
  });
  let body: string | undefined;
  if (request.method === "POST") {
    if (
      !process.env.NEXTAUTH_URL ||
      request.headers.get("origin") !== new URL(process.env.NEXTAUTH_URL).origin
    )
      return fail(403, "Request origin is not allowed.");
    if (!request.headers.get("content-type")?.startsWith("application/json"))
      return fail(415, "Use a JSON review request.");
    if (route.endsWith("/reviews")) {
      const key = request.headers.get("idempotency-key") ?? "";
      if (!uuid.test(key))
        return fail(422, "A valid review request key is required.");
      headers.set("Idempotency-Key", key);
    }
    const reader = request.body?.getReader();
    let size = 0;
    const chunks: Uint8Array[] = [];
    if (reader) {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        size += chunk.value.byteLength;
        if (size > 1048576) {
          await reader.cancel();
          return fail(413, "Review request is too large.");
        }
        chunks.push(chunk.value);
      }
    }
    const bytes = new Uint8Array(size);
    let position = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, position);
      position += chunk.byteLength;
    }
    body = new TextDecoder().decode(bytes);
    headers.set("Content-Type", "application/json");
  }
  const url = new URL(
    `/api/v1/organizations/${organizationId}/financial/${route}`,
    backend,
  );
  const incoming = new URL(request.url);
  if (incoming.search.length > 8192)
    return fail(414, "Exception query is too large.");
  for (const name of [
    "limit",
    "offset",
    "outcome",
    "current",
    "scope_key",
    "invoice_source_id",
    ...(route === "exception-facets" ? ["facet", "search"] : []),
    ...(route === "evaluations" || route === "exception-facets"
      ? [
          "invoice_document_id",
          "q",
          "decision_status",
          "currency",
          "supplier",
          "contract_source_id",
          "missing_contract",
          "created_from",
          "created_to",
          "needs_review",
          "sort",
          "pagination",
          "after",
        ]
      : []),
  ]) {
    const value = incoming.searchParams.get(name);
    if (value !== null) url.searchParams.set(name, value);
  }
  try {
    const response = await fetch(url, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(30000),
    });
    const outgoing = new Headers({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      "Content-Type": "application/json",
    });
    copyCorrelation(response.headers, outgoing);
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return fail(
      503,
      "Financial review is temporarily unavailable. Reload before retrying.",
    );
  }
}
