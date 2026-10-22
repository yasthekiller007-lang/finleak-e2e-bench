import "server-only";
import { getBackendAccessToken } from "@/lib/auth-server";
import {
  correlation,
  correlatedFailure,
  copyCorrelation,
} from "@/lib/proxy-correlation";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const fail = correlatedFailure;
export async function proxyProof(
  request: Request,
  org: string,
  path: string[],
) {
  const token = await getBackendAccessToken();
  if (!token) return fail(401, "Sign in to continue.");
  if (
    !uuid.test(org) ||
    !uuid.test(path[1] ?? "") ||
    path.some((p) => p.includes(".."))
  )
    return fail(404, "Resource not found.");
  const read =
    (path[0] === "evaluations" &&
      path.length === 3 &&
      path[2] === "packages") ||
    (path[0] === "packages" &&
      (path.length === 2 ||
        (path.length === 3 && ["history", "artifacts"].includes(path[2])) ||
        (path.length === 5 &&
          path[2] === "sources" &&
          uuid.test(path[3]) &&
          path[4] === "download"))) ||
    (path[0] === "artifacts" && path.length === 3 && path[2] === "download");
  const write =
    path.length === 3 &&
    ((path[0] === "evaluations" && path[2] === "generate") ||
      (path[0] === "packages" &&
        ["events", "export", "successor"].includes(path[2])));
  if (
    !(request.method === "GET" && read) &&
    !(request.method === "POST" && write)
  )
    return fail(405, "Method not allowed.");
  const backend = process.env.BACKEND_URL;
  if (!backend) return fail(503, "Proof service is not configured.");
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
    "X-Request-ID": correlation(request),
  });
  let body: Uint8Array | undefined;
  if (request.method === "POST") {
    if (
      !process.env.NEXTAUTH_URL ||
      request.headers.get("origin") !== new URL(process.env.NEXTAUTH_URL).origin
    )
      return fail(403, "Request origin is not allowed.");
    if (!request.headers.get("content-type")?.startsWith("application/json"))
      return fail(415, "Use JSON for proof requests.");
    const key = request.headers.get("idempotency-key") ?? "";
    if (!uuid.test(key))
      return fail(422, "A valid proof request key is required.");
    headers.set("Idempotency-Key", key);
    headers.set("Content-Type", "application/json");
    const reader = request.body?.getReader(),
      chunks: Uint8Array[] = [];
    let size = 0;
    if (reader) {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.byteLength;
        if (size > 1048576) {
          await reader.cancel();
          return fail(413, "Proof request is too large.");
        }
        chunks.push(part.value);
      }
    }
    body = new Uint8Array(size);
    let position = 0;
    for (const chunk of chunks) {
      body.set(chunk, position);
      position += chunk.byteLength;
    }
  }
  const url = new URL(
    `/api/v1/organizations/${org}/proof/${path.join("/")}`,
    backend,
  );
  const incoming = new URL(request.url);
  for (const name of ["limit", "offset"]) {
    const value = incoming.searchParams.get(name);
    if (value !== null) url.searchParams.set(name, value);
  }
  try {
    const response = await fetch(url, {
      method: request.method,
      headers,
      body: body as BodyInit | undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(30000),
    });
    const outgoing = new Headers({
      "Cache-Control": "no-store",
      "Content-Type":
        response.headers.get("content-type") ?? "application/json",
      "X-Content-Type-Options": "nosniff",
      "Content-Security-Policy": "sandbox",
    });
    for (const name of [
      "Idempotency-Key",
      "X-Artifact-SHA256",
      "X-Source-SHA256",
    ]) {
      const value = response.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    if (path.at(-1) === "download" && response.ok) {
      const filename =
        path[0] === "artifacts" ? `proof-${path[1]}.json` : `source-${path[3]}`;
      outgoing.set("Content-Disposition", `attachment; filename="${filename}"`);
    }
    copyCorrelation(response.headers, outgoing);
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return fail(
      503,
      "Proof service is temporarily unavailable. Retry the same request.",
    );
  }
}
