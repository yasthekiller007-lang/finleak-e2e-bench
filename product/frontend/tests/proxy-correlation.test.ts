// @vitest-environment node
import { expect, it } from "vitest";
import {
  correlation,
  correlatedFailure,
  copyCorrelation,
} from "@/lib/proxy-correlation";
const id = "00000000-0000-4000-8000-000000000001";
it("propagates only UUID correlation and bounded retry seconds", () => {
  const outgoing = new Headers();
  copyCorrelation(
    new Headers({
      "X-Request-ID": id,
      "Retry-After": "60",
      "set-cookie": "private",
    }),
    outgoing,
  );
  expect(outgoing.get("X-Request-ID")).toBe(id);
  expect(outgoing.get("Retry-After")).toBe("60");
  expect(outgoing.get("set-cookie")).toBeNull();
  copyCorrelation(
    new Headers({
      "X-Request-ID": "Bearer private-token",
      "Retry-After": "private-token",
    }),
    outgoing,
  );
  expect(outgoing.get("X-Request-ID")).toBe(id);
  expect(outgoing.get("Retry-After")).toBe("60");
  expect(
    correlation(
      new Request("https://app.test", { headers: { "X-Request-ID": id } }),
    ),
  ).toBe(id);
  expect(
    correlation(
      new Request("https://app.test", {
        headers: { "X-Request-ID": "private-token" },
      }),
    ),
  ).toMatch(/^[a-f0-9-]{36}$/);
});
it("gives local proxy failures a safe correlated envelope", async () => {
  const response = correlatedFailure(503, "Temporarily unavailable");
  expect((await response.json()).error.request_id).toBe(
    response.headers.get("X-Request-ID"),
  );
  expect(response.headers.get("Cache-Control")).toBe("no-store");
});
