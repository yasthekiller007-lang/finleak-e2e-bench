import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { RecoveryWorkspace } from "@/components/recovery-workspace";
import { sourceFields } from "@/lib/recovery";
import type { CurrentUser } from "@/lib/documents";
const user: CurrentUser = {
  id: "actor",
  email: null,
  display_name: "Actor",
  max_upload_bytes: 1024,
  organizations: [{ id: "org", name: "Internal tenant", role: "viewer" }],
};
const caseData = {
  id: "case-123456",
  evaluation_id: "eval",
  head_id: "head",
  currency: "USD",
  supplier: "supplier-A",
  customer: "buyer-A",
  lifecycle: "CLOSED",
  readiness: "BLOCKED",
  finding_decision: "confirmed",
  currentness: "CURRENT",
  evidence: "VERIFIED",
  realization_state: "PARTIAL",
  category: "ACTIVE_ELIGIBLE",
  coverage: "COMPLETE_RECORDED_LEDGER",
  potential: "50000.000000",
  validated: "50000.000000",
  pursuit: "50000.000000",
  claimed: null,
  acknowledged: null,
  disputed: null,
  realized: "30000.000000",
  methods: { CASH: "30000.000000" },
  net_cash: "29500.000000",
  pending_credit: null,
  unrealized: "20000.000000",
  ratio: "60.00",
  costs: { USD: { incurred: "500.000000", paid: "500.000000" } },
  readiness_record: null,
  workflow: null,
};
const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    fetchMock.mockReset().mockImplementation(async (url: string) => {
      if (url.includes("/cases/case-123456/history"))
        return Response.json({ items: [], has_more: false });
      if (url.endsWith("/cases/case-123456")) return Response.json(caseData);
      if (url.includes("/recovery/cases?"))
        return Response.json({ items: [caseData], has_more: false });
      return Response.json({ items: [], has_more: false });
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());
it("viewer reads independent money and blockers without authority controls", async () => {
  render(<RecoveryWorkspace user={user} />);
  fireEvent.click(await screen.findByRole("button", { name: /supplier-A/ }));
  await screen.findByText(
    "Gross verified realized recovery R — before separately evidenced costs",
  );
  expect(screen.getByText("Actual net bank cash N")).toBeInTheDocument();
  expect(screen.getByText("Unrealized pursuit balance")).toBeInTheDocument();
  expect(screen.getByText(/Positive authority is blocked/)).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Open investigation" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Close commercial pursuit" }),
  ).not.toBeInTheDocument();
  expect(
    fetchMock.mock.calls.every(
      ([url]) => !/generate|evaluate|process|export|successor/.test(url),
    ),
  ).toBe(true);
});
it("analyst prepares and operates workflow with no final monetary buttons", async () => {
  render(
    <RecoveryWorkspace
      user={{
        ...user,
        organizations: [{ ...user.organizations[0], role: "analyst" }],
      }}
    />,
  );
  fireEvent.click(await screen.findByRole("button", { name: /supplier-A/ }));
  await screen.findByText("Prepare reviewed proposal");
  expect(
    screen.getByRole("button", { name: "Update workflow" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Close commercial pursuit" }),
  ).not.toBeInTheDocument();
});
it("owner sees explicit lifecycle while known zero and null remain distinct", async () => {
  render(
    <RecoveryWorkspace
      user={{
        ...user,
        organizations: [{ ...user.organizations[0], role: "owner" }],
      }}
    />,
  );
  fireEvent.click(await screen.findByRole("button", { name: /supplier-A/ }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument(),
  );
  expect(
    screen.getByText("Costs are not subtracted from R.", { exact: false }),
  ).toBeInTheDocument();
  expect(screen.getAllByText("Unknown / not recorded").length).toBeGreaterThan(
    0,
  );
});
it("evidence mappings preserve Decimal scale and boolean meaning", () => {
  expect(
    sourceFields({
      principal: "0.01",
      rate: "18.40",
      completed: true,
      tax: null,
      economic: { precision: "DATE", day: "2026-12-31" },
    }),
  ).toEqual({
    "/value/principal": "0.01",
    "/value/rate": "18.40",
    "/value/completed": "True",
    "/value/economic/precision": "DATE",
    "/value/economic/day": "2026-12-31",
  });
});
it("history distinguishes unresolved commit provenance and pages without totaling pages", async () => {
  fetchMock.mockImplementation(async (url: string) => {
    if (url.includes("/cases/case-123456/history"))
      return Response.json({
        items: [
          {
            id: "event",
            kind: "note",
            number: 1,
            actor_id: "actor",
            created_at: "2026-01-01",
            known_at: null,
            value: {},
            reason: "Attribution",
          },
        ],
        has_more: !url.includes("offset=100"),
      });
    if (url.endsWith("/cases/case-123456")) return Response.json(caseData);
    if (url.includes("/recovery/cases?"))
      return Response.json({ items: [caseData], has_more: false });
    return Response.json({ items: [], has_more: false });
  });
  render(<RecoveryWorkspace user={user} />);
  fireEvent.click(await screen.findByRole("button", { name: /supplier-A/ }));
  await screen.findByText(/unresolved commit provenance/);
  fireEvent.click(screen.getByRole("button", { name: "Next history" }));
  await waitFor(() =>
    expect(
      fetchMock.mock.calls.some(([url]) =>
        url.includes("history?limit=100&offset=100"),
      ),
    ).toBe(true),
  );
  expect(
    screen.getByText(/complete monetary projections are shown separately/),
  ).toBeInTheDocument();
});
it("removes old authority controls and measures after a failed history refresh", async () => {
  const owner = {
    ...user,
    organizations: [{ ...user.organizations[0], role: "owner" as const }],
  };
  let fail = false;
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((url: string) => {
    if (url.includes("/history")) {
      if (fail)
        return Promise.resolve(
          Response.json(
            { error: { message: "History unavailable" } },
            { status: 503 },
          ),
        );
      return Promise.resolve(Response.json({ items: [], has_more: true }));
    }
    return original(url);
  });
  render(<RecoveryWorkspace user={owner} />);
  fireEvent.click(await screen.findByRole("button", { name: /supplier-A/ }));
  await screen.findByText("Actual net bank cash N");
  fail = true;
  fireEvent.click(screen.getByRole("button", { name: "Next history" }));
  await screen.findByRole("alert");
  expect(screen.queryByText("Actual net bank cash N")).toBeNull();
  expect(screen.queryByRole("button", { name: "Reopen" })).toBeNull();
});
it("keeps a history outage visible when the companion case-list refresh succeeds later", async () => {
  let refreshing = false;
  let completeList: (() => void) | undefined;
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((url: string) => {
    if (url.endsWith("/inspect")) {
      refreshing = true;
      return Promise.resolve(Response.json({ id: "observation" }));
    }
    if (refreshing && url.includes("/recovery/cases?"))
      return new Promise<Response>((resolve) => {
        completeList = () =>
          resolve(Response.json({ items: [caseData], has_more: false }));
      });
    if (refreshing && url.includes("/history"))
      return Promise.resolve(
        Response.json(
          { error: { message: "History unavailable" } },
          { status: 503 },
        ),
      );
    return original(url);
  });
  render(
    <RecoveryWorkspace
      user={{
        ...user,
        organizations: [{ ...user.organizations[0], role: "owner" }],
      }}
    />,
  );
  fireEvent.click(await screen.findByRole("button", { name: /supplier-A/ }));
  await screen.findByText("Actual net bank cash N");
  fireEvent.change(screen.getByLabelText("Action / approval reason"), {
    target: { value: "Review current readiness" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Record current readiness inspection" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "History unavailable",
  );
  await act(async () => completeList!());
  await screen.findByRole("button", { name: /supplier-A/ });
  expect(screen.getByRole("alert")).toHaveTextContent("History unavailable");
  expect(screen.queryByText("Actual net bank cash N")).toBeNull();
  expect(screen.queryByRole("button", { name: "Reopen" })).toBeNull();
  expect(
    screen.queryByText(
      "Current authority observation preserved for as-known reporting.",
    ),
  ).toBeNull();
});
