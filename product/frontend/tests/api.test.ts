import { afterEach, describe, expect, it, vi } from "vitest";
import { getServiceHealth } from "@/lib/api";

vi.mock("server-only", () => ({}));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("API readiness boundary", () => {
  it("reports an unconfigured API without making a request", async () => {
    vi.stubEnv("BACKEND_URL", "");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect(await getServiceHealth()).toBe("unknown");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("checks the actual database readiness response", async () => {
    vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ status: "ready" }) });
    vi.stubGlobal("fetch", fetchMock);
    expect(await getServiceHealth()).toBe("ready");
    expect(fetchMock.mock.calls[0][0].pathname).toBe("/api/v1/health/ready");
  });

  it("reports a failed database check as unavailable", async () => {
    vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    expect(await getServiceHealth()).toBe("unavailable");
  });

  it("handles unreachable services", async () => {
    vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Connection failed")),
    );
    expect(await getServiceHealth()).toBe("unavailable");
  });
});
