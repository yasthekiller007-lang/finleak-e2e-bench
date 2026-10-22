import "server-only";
import { getBackendAccessToken } from "@/lib/auth-server";
import {
  correlation,
  correlatedFailure,
  copyCorrelation,
} from "@/lib/proxy-correlation";

const fail = correlatedFailure;

export async function proxyDocuments(
  request: Request,
  organizationId: string,
  documentId?: string,
  content = false,
) {
  const token = await getBackendAccessToken();
  if (!token) return fail(401, "Sign in to continue.");
  const uuid =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!uuid.test(organizationId) || (documentId && !uuid.test(documentId)))
    return fail(404, "Resource not found.");
  const backend = process.env.BACKEND_URL;
  if (!backend) return fail(503, "Document service is not configured.");
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
    "X-Request-ID": correlation(request),
  });
  let body: ReadableStream<Uint8Array> | undefined;
  if (request.method === "POST") {
    // These endpoints use browser cookies, so mutations additionally enforce same-origin.
    if (
      !process.env.NEXTAUTH_URL ||
      request.headers.get("origin") !== new URL(process.env.NEXTAUTH_URL).origin
    )
      return fail(403, "Request origin is not allowed.");
    const contentType = request.headers.get("content-type") ?? "";
    if (!contentType.startsWith("multipart/form-data"))
      return fail(415, "Use multipart/form-data.");
    headers.set("Content-Type", contentType);
    const configuredLimit = Number(
      process.env.FLA_MAX_UPLOAD_BYTES ?? 20971520,
    );
    if (
      !Number.isInteger(configuredLimit) ||
      configuredLimit < 1024 ||
      configuredLimit > 104857600
    )
      return fail(503, "Upload service is not configured.");
    const maxBytes = configuredLimit + 1048576;
    let received = 0;
    body = request.body?.pipeThrough(
      new TransformStream({
        transform(chunk, controller) {
          received += chunk.byteLength;
          if (received > maxBytes) throw new Error("upload_body_limit");
          controller.enqueue(chunk);
        },
      }),
    );
  }
  const path = `/api/v1/organizations/${organizationId}/documents${documentId ? `/${documentId}` : ""}${content ? "/content" : ""}`;
  const url = new URL(path, backend);
  const incoming = new URL(request.url);
  for (const param of ["limit", "offset"])
    if (incoming.searchParams.has(param))
      url.searchParams.set(param, incoming.searchParams.get(param)!);
  try {
    const response = await fetch(url, {
      method: request.method,
      headers,
      body,
      duplex: "half",
      cache: "no-store",
      signal: AbortSignal.timeout(30000),
    } as RequestInit);
    const safeHeaders = new Headers({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    for (const name of [
      "content-type",
      "content-disposition",
      "content-length",
      "content-security-policy",
    ]) {
      const value = response.headers.get(name);
      if (value) safeHeaders.set(name, value);
    }
    copyCorrelation(response.headers, safeHeaders);
    return new Response(response.body, {
      status: response.status,
      headers: safeHeaders,
    });
  } catch (error) {
    if (
      error instanceof Error &&
      (error.message === "upload_body_limit" ||
        (error.cause instanceof Error &&
          error.cause.message === "upload_body_limit"))
    )
      return fail(413, "Request exceeds the maximum upload size.");
    return fail(503, "Document service is temporarily unavailable.");
  }
}
