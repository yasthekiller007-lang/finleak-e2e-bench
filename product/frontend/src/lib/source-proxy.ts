import "server-only";
import { getBackendAccessToken } from "@/lib/auth-server";
import {
  correlation,
  correlatedFailure as fail,
  copyCorrelation,
} from "@/lib/proxy-correlation";

const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
export async function proxySource(
  request: Request,
  org: string,
  doc: string,
  action: string,
) {
  const token = await getBackendAccessToken();
  if (!token) return fail(401, "Sign in to continue.");
  if (
    !uuid.test(org) ||
    !uuid.test(doc) ||
    !["source-status", "scan", "release"].includes(action)
  )
    return fail(404, "Resource not found.");
  const write = action !== "source-status";
  if (request.method !== (write ? "POST" : "GET"))
    return fail(405, "Method not allowed.");
  if (!process.env.BACKEND_URL)
    return fail(503, "Source service is not configured.");
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
    "X-Request-ID": correlation(request),
  });
  let body: string | undefined;
  if (write) {
    if (
      !process.env.NEXTAUTH_URL ||
      request.headers.get("origin") !== new URL(process.env.NEXTAUTH_URL).origin
    )
      return fail(403, "Request origin is not allowed.");
    if (
      request.headers.get("content-type")?.split(";")[0].trim() !==
      "application/json"
    )
      return fail(415, "Use a JSON source request.");
    const key = request.headers.get("idempotency-key") ?? "";
    if (!uuid.test(key))
      return fail(422, "A valid source request key is required.");
    const reader = request.body?.getReader();
    if (!reader) return fail(422, "A source action reason is required.");
    const chunks: Uint8Array[] = [];
    let size = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      await Promise.race([
        (async () => {
          while (true) {
            const chunk = await reader.read();
            if (chunk.done) break;
            size += chunk.value.byteLength;
            if (size > 16384) throw new Error("size");
            chunks.push(chunk.value);
          }
        })(),
        new Promise((_, reject) => {
          timer = setTimeout(() => reject(new Error("deadline")), 10000);
        }),
      ]);
      const bytes = new Uint8Array(size);
      let position = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, position);
        position += chunk.byteLength;
      }
      const parsed = JSON.parse(
        new TextDecoder("utf-8", { fatal: true }).decode(bytes),
      );
      if (
        !parsed ||
        typeof parsed.reason !== "string" ||
        !parsed.reason.trim() ||
        parsed.reason.length > 4000 ||
        Object.keys(parsed).some(
          (k) =>
            !["reason", ...(action === "release" ? ["scan_id"] : [])].includes(
              k,
            ),
        ) ||
        (action === "release" &&
          (typeof parsed.scan_id !== "string" || !uuid.test(parsed.scan_id)))
      )
        return fail(
          422,
          "Use a reason and the current clean scan for release.",
        );
      body = JSON.stringify(parsed);
    } catch (cause) {
      return fail(
        cause instanceof Error && cause.message === "size" ? 413 : 422,
        "Source request is invalid, too large, or incomplete.",
      );
    } finally {
      clearTimeout(timer);
      void reader.cancel().catch(() => {});
    }
    headers.set("Idempotency-Key", key);
    headers.set("Content-Type", "application/json");
  }
  try {
    const response = await fetch(
      new URL(
        `/api/v1/organizations/${org}/documents/${doc}/${action}`,
        process.env.BACKEND_URL,
      ),
      {
        method: request.method,
        headers,
        body,
        cache: "no-store",
        signal: AbortSignal.timeout(action === "scan" ? 150000 : 30000),
      },
    );
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
      "Source service is unavailable. Refresh before retrying the same request.",
    );
  }
}
