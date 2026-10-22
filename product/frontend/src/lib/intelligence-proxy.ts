import "server-only";
import { getBackendAccessToken } from "@/lib/auth-server";
import {
  correlation,
  correlatedFailure,
  copyCorrelation,
} from "@/lib/proxy-correlation";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const fail = correlatedFailure;
export async function proxyIntelligence(
  request: Request,
  organizationId: string,
  documentId: string,
  action: string,
  runId?: string,
) {
  const token = await getBackendAccessToken();
  if (!token) return fail(401, "Sign in to continue.");
  if (
    !uuid.test(organizationId) ||
    !uuid.test(documentId) ||
    (runId && !uuid.test(runId))
  )
    return fail(404, "Resource not found.");
  const write = action === "process" || action === "reprocess";
  if (
    (!write && !["extraction", "extraction-runs"].includes(action)) ||
    (runId && action !== "extraction-runs")
  )
    return fail(404, "Resource not found.");
  if (request.method !== (write ? "POST" : "GET"))
    return fail(405, "Method not allowed.");
  const backend = process.env.BACKEND_URL;
  if (!backend) return fail(503, "Document service is not configured.");
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
    "X-Request-ID": correlation(request),
  });
  if (write) {
    if (
      !process.env.NEXTAUTH_URL ||
      request.headers.get("origin") !== new URL(process.env.NEXTAUTH_URL).origin
    )
      return fail(403, "Request origin is not allowed.");
    const key = request.headers.get("idempotency-key") ?? "";
    if (!uuid.test(key)) return fail(422, "A valid request key is required.");
    // Processing uses the already stored file. Do not accept document instructions or payloads.
    if (request.body) {
      const reader = request.body.getReader();
      let chunk;
      do {
        chunk = await reader.read();
      } while (!chunk.done && chunk.value.byteLength === 0);
      await reader.cancel();
      if (!chunk.done)
        return fail(422, "This action does not accept a request body.");
    }
    headers.set("Idempotency-Key", key);
  }
  try {
    const url = new URL(
      `/api/v1/organizations/${organizationId}/documents/${documentId}/${action}${runId ? `/${runId}` : ""}`,
      backend,
    );
    if (action === "extraction-runs" && !runId) {
      const incoming = new URL(request.url);
      for (const parameter of ["limit", "offset"]) {
        const value = incoming.searchParams.get(parameter);
        if (value !== null) url.searchParams.set(parameter, value);
      }
    }
    const response = await fetch(url, {
      method: request.method,
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(150000),
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
      "Document service is temporarily unavailable. Refresh before retrying.",
    );
  }
}
