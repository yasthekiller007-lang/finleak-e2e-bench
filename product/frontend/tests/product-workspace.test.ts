// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  activitySeries,
  exposureShare,
  liveWorkspaceGateway,
  WorkspaceError,
} from "@/lib/product-workspace";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { money } from "@/lib/financial";

const org = demoUser.organizations[0].id;
const signal = () => new AbortController().signal;
const fetchMock = vi.fn();
beforeEach(() => vi.stubGlobal("fetch", fetchMock.mockReset()));
afterEach(() => vi.unstubAllGlobals());

describe("existing BFF contract integration", () => {
  it("loads the four existing tenant-scoped APIs without browser bearer credentials", async () => {
    const data = await createDemoGateway().load(org, signal());
    fetchMock.mockImplementation(async (url: string) =>
      Response.json(
        url.includes("/summary")
          ? data.summary
          : url.includes("/documents?")
            ? data.documents
            : url.includes("/sources?")
              ? data.sources
              : data.assessments,
      ),
    );
    expect(await liveWorkspaceGateway.load(org, signal())).toEqual(data);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      `/api/organizations/${org}/financial/summary`,
      `/api/organizations/${org}/documents?limit=100&offset=0`,
      `/api/organizations/${org}/financial/sources?limit=100&offset=0`,
      `/api/organizations/${org}/financial/evaluations?limit=100&offset=0`,
    ]);
    for (const [, options] of fetchMock.mock.calls) {
      expect(options).toMatchObject({
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
      });
      expect(options.headers).toBeUndefined();
    }
  });
  it("posts exactly the allowed finding decision and its actual predecessor", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ id: "decision-id" }, { status: 201 }),
    );
    const decision = {
      status: "false_positive" as const,
      reason: "Contract amendment reviewed",
      expected_decision: "previous-decision-id",
    };
    await liveWorkspaceGateway.decide(org, "evaluation-id", decision, signal());
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/organizations/${org}/financial/evaluations/evaluation-id/decision`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(decision),
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
  it.each([401, 409, 503])(
    "preserves an HTTP %i failure without synthetic fallback",
    async (status) => {
      fetchMock.mockResolvedValue(
        Response.json(
          { error: { message: "Service unavailable" } },
          { status, headers: { "X-Request-ID": "correlation-id" } },
        ),
      );
      await expect(
        liveWorkspaceGateway.assessment(org, "id", signal()),
      ).rejects.toMatchObject({ status, requestId: "correlation-id" });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    },
  );
  it("reads existing immutable proof and history without issuing a package", async () => {
    fetchMock.mockImplementation(async (url: string) =>
      Response.json(
        url.includes("/evaluations/")
          ? { items: [{ id: "package-id" }], has_more: true }
          : url.includes("/history?")
            ? { items: [], has_more: false }
            : { id: "package-id", fingerprint: "recorded-digest" },
      ),
    );
    const proof = await liveWorkspaceGateway.proof(org, "eval-id", signal());
    expect(proof.proof?.fingerprint).toBe("recorded-digest");
    expect(proof.hasMorePackages).toBe(true);
    expect(
      fetchMock.mock.calls.every(([, options]) => options.method === "GET"),
    ).toBe(true);
    expect(fetchMock.mock.calls[2][0]).toContain(
      "/proof/packages/package-id/history?limit=100&offset=0",
    );
  });
  it("represents absent issued proof explicitly", async () => {
    fetchMock.mockResolvedValue(Response.json({ items: [], has_more: false }));
    expect(await liveWorkspaceGateway.proof(org, "eval-id", signal())).toEqual({
      proof: null,
      history: null,
      hasMorePackages: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("financial presentation and isolated synthetic workspace", () => {
  it("keeps exact six-decimal strings and never converts or nets currencies", () => {
    expect(money("99999999999999.123456", "USD")).toBe(
      "99,999,999,999,999.123456 USD",
    );
    expect(money(null, "EUR")).toBe("Not assessed");
    expect(money("0.000000", "EUR")).toBe("0.00 EUR");
    expect(
      exposureShare("99999999999999.123456", "199999999999998.246912"),
    ).toBe(50);
    expect(exposureShare("0.000001", "0.000002")).toBe(50);
    expect(exposureShare("1", "0")).toBe(0);
    expect(exposureShare("-1", "2")).toBe(0);
    expect(exposureShare("1e10", "2")).toBe(0);
  });
  it("uses actual dated assessment counts and ignores invalid timestamps", async () => {
    const data = await createDemoGateway().load(org, signal());
    expect(
      activitySeries([
        ...data.assessments.items,
        { ...data.assessments.items[0], created_at: "not-a-date" },
      ]),
    ).toEqual([
      ["2026-10-14", 1],
      ["2026-10-15", 1],
      ["2026-10-16", 1],
      ["2026-10-17", 1],
    ]);
  });
  it("keeps demo decisions in one instance, checks concurrency and makes zero API calls", async () => {
    const demo = createDemoGateway(),
      fresh = createDemoGateway();
    const { assessments } = await demo.load(org, signal());
    const a = assessments.items[0];
    await demo.decide(
      org,
      a.id,
      {
        status: "false_positive",
        reason: "Synthetic exercise",
        expected_decision: null,
      },
      signal(),
    );
    expect(
      (await demo.load(org, signal())).summary.potential_by_currency,
    ).toEqual({ USD: "2880.000000", EUR: "1380.000000" });
    expect((await fresh.assessment(org, a.id, signal())).status).toBe(
      "detected",
    );
    await expect(
      demo.decide(
        org,
        a.id,
        {
          status: "confirmed",
          reason: "Stale exercise",
          expected_decision: null,
        },
        signal(),
      ),
    ).rejects.toBeInstanceOf(WorkspaceError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
