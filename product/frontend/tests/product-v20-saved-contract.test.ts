import { afterEach, expect, it, vi } from "vitest";
import {
  savedDefinition,
  savedName,
  parseSavedView,
  liveSavedViewsGateway,
} from "@/lib/saved-views";
const org = "00000000-0000-4000-8000-000000000001",
  owner = "00000000-0000-4000-8000-000000000002",
  id = "00000000-0000-4000-8000-000000000003";
const definition = {
  view_type: "anomalies",
  format_version: 1,
  criteria: { currency: "USD", needs_review: false, sort: "newest" },
  page_size: 20,
};
const row = {
  ...definition,
  id,
  organization_id: org,
  user_id: owner,
  name: "CFO USD",
  revision: 1,
  created_at: "2026-10-19T00:00:00Z",
  updated_at: "2026-10-19T00:00:00Z",
};
afterEach(() => vi.unstubAllGlobals());
it.each(["", "  ", "x".repeat(81), "bad\nname", "bad\u202ename"])(
  "rejects invalid saved name %j",
  (name) => expect(() => savedName(name)).toThrow(),
);
it("normalizes readable names without pretending to enforce server uniqueness", () =>
  expect(savedName("  ＣＦＯ  USD ")).toBe("CFO USD"));
it.each([
  "amount",
  "token",
  "after",
  "decision",
  "reason",
  "citations",
  "url",
  "user_id",
])("rejects unsupported stored criterion %s", (key) =>
  expect(() =>
    savedDefinition({ ...definition, criteria: { [key]: "bad" } }),
  ).toThrow(),
);
it.each([
  { ...definition, format_version: 2 },
  { ...definition, page_size: 2 },
  { ...definition, view_type: "dashboard" },
  { ...definition, criteria: { current: "true" } },
  { ...definition, criteria: { supplier: null } },
  {
    ...definition,
    criteria: { contract_source_id: id, missing_contract: true },
  },
  { ...definition, criteria: { created_from: "2026-02-30T00:00:00Z" } },
])("rejects incompatible saved definitions", (value) =>
  expect(() => savedDefinition(value)).toThrow(),
);
it("preserves review defaults and explicit false override", () => {
  expect(
    savedDefinition({ ...definition, view_type: "review", criteria: {} })
      .criteria.needs_review,
  ).toBe(true);
  expect(
    savedDefinition({ ...definition, view_type: "review" }).criteria
      .needs_review,
  ).toBe(false);
});
it.each([
  { ...row, organization_id: id },
  { ...row, user_id: id },
  { ...row, revision: 0 },
  { ...row, format_version: 2 },
  { ...row, token: "secret" },
])("refuses a response from a different scope or unknown format", (value) =>
  expect(() => parseSavedView(value, org, owner)).toThrow(),
);
it("posts structured criteria without owner, session, labels, results or cursor", async () => {
  const f = vi.fn().mockResolvedValue(Response.json(row));
  vi.stubGlobal("fetch", f);
  await liveSavedViewsGateway.create(
    org,
    owner,
    "CFO USD",
    savedDefinition(definition),
    new AbortController().signal,
  );
  const [, options] = f.mock.calls[0];
  expect(JSON.parse(options.body)).toEqual({
    name: "CFO USD",
    ...savedDefinition(definition),
  });
  expect(options.method).toBe("POST");
  expect(options.credentials).toBe("same-origin");
  expect(options.cache).toBe("no-store");
});
it("uses PATCH for a name only and DELETE with expected revision", async () => {
  const f = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ ...row, name: "New", revision: 2 }))
    .mockResolvedValueOnce(Response.json({ id, deleted: true }));
  vi.stubGlobal("fetch", f);
  const signal = new AbortController().signal;
  await liveSavedViewsGateway.update(
    org,
    owner,
    id,
    1,
    { name: "New" },
    signal,
  );
  await liveSavedViewsGateway.remove(org, owner, id, 2, signal);
  expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({
    expected_revision: 1,
    name: "New",
  });
  expect(f.mock.calls[1][1].method).toBe("DELETE");
  expect(JSON.parse(f.mock.calls[1][1].body)).toEqual({ expected_revision: 2 });
});
it("rejects oversized list responses and never automatically retries failed writes", async () => {
  const f = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        items: Array(11).fill(row),
        limit: 10,
        max_views: 50,
        has_more: false,
        next_after: null,
      }),
    )
    .mockResolvedValueOnce(
      Response.json(
        { error: { code: "SAVED_VIEW_CONFLICT", message: "Conflict" } },
        { status: 409 },
      ),
    );
  vi.stubGlobal("fetch", f);
  const signal = new AbortController().signal;
  await expect(
    liveSavedViewsGateway.list(org, owner, "anomalies", "", null, signal),
  ).rejects.toThrow();
  await expect(
    liveSavedViewsGateway.update(org, owner, id, 1, { name: "New" }, signal),
  ).rejects.toMatchObject({ status: 409, code: "SAVED_VIEW_CONFLICT" });
  expect(f).toHaveBeenCalledTimes(2);
});

it("rejects unsafe stored text before list rendering", () =>
  expect(() =>
    savedDefinition({ ...definition, criteria: { q: "bad\u202etext" } }),
  ).toThrow());
