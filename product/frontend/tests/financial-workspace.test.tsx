import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { FinancialWorkspace } from "@/components/financial-workspace";
import type { CurrentUser } from "@/lib/documents";
const user: CurrentUser = {
  id: "reviewer",
  email: null,
  display_name: "Reviewer",
  max_upload_bytes: 100,
  organizations: [{ id: "org", name: "Enterprise", role: "owner" }],
};
const source = { id: "invoice", document_id: "doc", kind: "invoice" };
const record = {
  id: "review",
  kind: "billing_scope",
  key: "line-1",
  state: "prepared",
  actor_id: "reviewer",
  created_at: "2026-10-03",
  payload: {
    value: { posted_amount: "1200" },
    evidence: [],
    reason: "Reviewed",
    uncertainty_resolution: "Resolved",
  },
  provenance: [],
};
const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    fetchMock.mockReset().mockImplementation((url: string) => {
      if (url.includes("/summary"))
        return Promise.resolve(
          Response.json({
            potential_by_currency: { USD: "200.000000" },
            counts: { findings: 1, blocked: 1, assessed: 0, stale: 1 },
            limited: false,
            coverage: "Blocked and unassessed amounts are unknown.",
          }),
        );
      if (url.endsWith("sources/invoice"))
        return Promise.resolve(
          Response.json({
            ...source,
            reviews: [record],
            approved_inputs: [],
            revision_ids: ["revision"],
          }),
        );
      if (url.includes("/sources"))
        return Promise.resolve(Response.json({ items: [source], total: 1 }));
      if (url.includes("/evaluations"))
        return Promise.resolve(
          Response.json({
            items: [
              {
                id: "blocked",
                scope_key: "line-2",
                explanation: "Review missing pricing schedule.",
                expected: null,
                actual: null,
                potential: null,
                currency: null,
                status: null,
                stale: false,
                outcome: "NEEDS_REVIEW",
              },
            ],
            total: 1,
          }),
        );
      return Promise.resolve(
        Response.json({
          items: [
            {
              id: "doc",
              original_filename: "invoice.csv",
              document_type: "invoice",
            },
          ],
          total: 1,
        }),
      );
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());
it("shows currency-specific potential and explicit blocked coverage", async () => {
  render(<FinancialWorkspace user={user} />);
  expect(await screen.findByText("200.00 USD")).toBeInTheDocument();
  expect(
    screen.getByText("Blocked and unassessed amounts are unknown."),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Review missing pricing schedule."),
  ).toBeInTheDocument();
  expect(screen.getByText(/Contracted Not assessed/)).toBeInTheDocument();
});
it.each(["owner", "admin", "analyst", "viewer"] as const)(
  "enforces review affordances for %s",
  async (role) => {
    render(
      <FinancialWorkspace
        user={{ ...user, organizations: [{ ...user.organizations[0], role }] }}
      />,
    );
    await screen.findByText("200.00 USD");
    fireEvent.change(screen.getByLabelText("Reviewed source"), {
      target: { value: "invoice" },
    });
    await screen.findByText("Reviewed values and supporting source");
    const authority = role === "owner" || role === "admin";
    expect(
      screen.queryByRole("button", { name: "Record authority decision" }) !==
        null,
    ).toBe(authority);
    expect(
      screen.queryByRole("button", { name: "Save prepared review" }) !== null,
    ).toBe(role !== "viewer");
  },
);
it("submits owner decisions with predecessor and never exposes a browser token", async () => {
  render(<FinancialWorkspace user={user} />);
  await screen.findByText("200.00 USD");
  fireEvent.change(screen.getByLabelText("Reviewed source"), {
    target: { value: "invoice" },
  });
  await screen.findByText("Reviewed values and supporting source");
  fireEvent.change(screen.getByLabelText("Decision reason"), {
    target: { value: "Evidence verified" },
  });
  fireEvent.click(
    screen.getByLabelText(
      "I verified source, scope, exceptions and resolved uncertainty.",
    ),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Record authority decision" }),
  );
  await waitFor(() =>
    expect(
      fetchMock.mock.calls.some(
        ([url, options]) =>
          String(url).endsWith("/reviews") &&
          JSON.parse(options.body).expected_revision === "review",
      ),
    ).toBe(true),
  );
  const call = fetchMock.mock.calls.find(([url]) =>
    String(url).endsWith("/reviews"),
  );
  expect(call?.[1].headers.Authorization).toBeUndefined();
});
