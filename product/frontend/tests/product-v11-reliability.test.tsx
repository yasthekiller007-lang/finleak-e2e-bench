import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FinancialDecisionPanel } from "@/components/financial-decision-panel";
import { FinancialDecisionAudit } from "@/components/financial-decision-audit";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { createReliabilityDemoGateway } from "@/lib/product-demo-reliability";
import {
  WorkspaceError,
  liveWorkspaceGateway,
  type WorkspaceGateway,
} from "@/lib/product-workspace";
const org = demoUser.organizations[0].id,
  signal = () => new AbortController().signal;
async function setup(gateway = createDemoGateway(), role = "owner") {
  const data = await gateway.load(org, signal()),
    detail = data.assessments.items[0];
  const updated = vi.fn();
  render(
    <FinancialDecisionPanel
      detail={detail}
      orgId={org}
      role={role}
      gateway={gateway}
      demo={false}
      status={<span>Recorded status</span>}
      onDecision={updated}
    />,
  );
  return { gateway, detail, updated };
}
function submit() {
  fireEvent.change(screen.getByLabelText("Reason for decision"), {
    target: { value: "Synthetic contractual evidence checked" },
  });
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(
    screen.getByRole("button", { name: "Record financial decision" }),
  );
}

describe("financial decision write reliability (controlled fixtures; not PostgreSQL E2E)", () => {
  it("matches a receipt by an independent read and locks accidental resubmission", async () => {
    const g = createDemoGateway(),
      post = vi.spyOn(g, "decide");
    await setup(g);
    submit();
    await screen.findByText(
      "Decision recorded. Historical calculations and evidence remain unchanged.",
    );
    expect(
      screen.getByRole("button", { name: "Record financial decision" }),
    ).toBeDisabled();
    fireEvent.click(
      screen.getByRole("button", { name: "Record financial decision" }),
    );
    expect(post).toHaveBeenCalledTimes(1);
    fireEvent.click(
      screen.getByRole("button", { name: "Prepare another decision" }),
    );
    expect(screen.getByLabelText("Reason for decision")).toHaveValue("");
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });
  it("reconciles a lost response without another POST or an invented authorship claim", async () => {
    const g = createReliabilityDemoGateway("lost-response"),
      post = vi.spyOn(g, "decide");
    await setup(g);
    submit();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "save outcome is unknown",
    );
    expect(
      screen.getByRole("button", { name: "Record financial decision" }),
    ).toBeDisabled();
    fireEvent.click(
      screen.getByRole("button", { name: "Reload current decision" }),
    );
    await screen.findByText(/A changed ID alone does not establish/);
    expect(post).toHaveBeenCalledTimes(1);
    const page = await g.audit!(org, signal());
    expect(page.total).toBe(1);
    expect(
      screen.queryByText(
        "Decision recorded. Historical calculations and evidence remain unchanged.",
      ),
    ).not.toBeInTheDocument();
  });
  it("distinguishes acknowledgment from an unavailable follow-up read", async () => {
    const g = createReliabilityDemoGateway("read-failure"),
      post = vi.spyOn(g, "decide");
    await setup(g);
    submit();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "backend acknowledged this decision",
    );
    expect(screen.getByText(/Backend acknowledgment/)).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Reload current decision" }),
    );
    await screen.findByText(
      "Decision recorded. Historical calculations and evidence remain unchanged.",
    );
    expect(post).toHaveBeenCalledTimes(1);
  });
  it("locks a 409 until a read and explicit new review intent", async () => {
    const g = createReliabilityDemoGateway("conflict"),
      post = vi.spyOn(g, "decide");
    await setup(g);
    submit();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No automatic retry",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Reload current decision" }),
    );
    await screen.findByRole("button", { name: "Prepare another decision" });
    expect(post).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Finding decision")).toBeDisabled();
  });
  it("keeps a failed reconciliation locked without retrying a write", async () => {
    const g = createDemoGateway();
    g.decide = vi.fn().mockRejectedValue(new Error("connection lost"));
    g.assessment = vi.fn().mockRejectedValue(new Error("database unavailable"));
    await setup(g);
    submit();
    await screen.findByRole("button", { name: "Reload current decision" });
    fireEvent.click(
      screen.getByRole("button", { name: "Reload current decision" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No write was retried",
    );
    expect(g.decide).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("button", { name: "Record financial decision" }),
    ).toBeDisabled();
  });
  it.each([401, 403])(
    "locks a server rejection HTTP %i without weakening role checks",
    async (status) => {
      const g = createDemoGateway();
      g.decide = vi
        .fn()
        .mockRejectedValue(new WorkspaceError("Access rejected", status));
      await setup(g);
      submit();
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Submission is locked",
      );
      expect(
        screen.getByRole("link", { name: "Return to sign in" }),
      ).toHaveAttribute("href", "/login");
    },
  );
  it("rejects an unverifiable success payload instead of claiming persistence", async () => {
    const g = createDemoGateway();
    g.decide = vi.fn().mockResolvedValue({ status: "confirmed" });
    await setup(g);
    submit();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "response could not be verified",
    );
    expect(screen.queryByText(/Decision recorded\./)).not.toBeInTheDocument();
  });
  it("does not confuse a newer concurrent decision with its own receipt", async () => {
    const g = createDemoGateway(),
      read = g.assessment;
    g.assessment = async (...args) => ({
      ...(await read(...args)),
      decision_id: "00000000-0000-4000-8000-000000009999",
      status: "needs_review",
    });
    await setup(g);
    submit();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "latest decision differs",
    );
    expect(screen.queryByText(/Decision recorded\./)).not.toBeInTheDocument();
  });
  it("blocks a rapid duplicate submit while a first write is pending", async () => {
    const g = createDemoGateway();
    let resolve!: (v: unknown) => void;
    g.decide = vi.fn(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    await setup(g);
    submit();
    const form = screen.getByLabelText("Reason for decision").closest("form")!;
    fireEvent.submit(form);
    expect(g.decide).toHaveBeenCalledTimes(1);
    await act(async () => resolve({}));
  });
  it("reopening the assessment reads its saved overlay without a write", async () => {
    const g = createDemoGateway(),
      data = await g.load(org, signal());
    await g.decide(
      org,
      data.assessments.items[0].id,
      {
        status: "confirmed",
        reason: "Synthetic prior action",
        expected_decision: null,
      },
      signal(),
    );
    const post = vi.spyOn(g, "decide");
    await setup(g);
    expect(post).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Record financial decision" }),
    ).toBeDisabled();
  });
});

describe("existing financial audit read", () => {
  it("reads the existing audit endpoint with no browser bearer token", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        Response.json({ items: [], total: 0, limit: 100, offset: 0 }),
      );
    try {
      await liveWorkspaceGateway.audit!(org, signal());
      expect(fetcher).toHaveBeenCalledWith(
        `/api/organizations/${org}/financial/audit?limit=100&offset=0`,
        expect.objectContaining({ method: "GET", credentials: "same-origin" }),
      );
      expect(fetcher.mock.calls[0][1]?.headers).toBeUndefined();
    } finally {
      fetcher.mockRestore();
    }
  });
  it("displays only the current decision audit with its returned actor, reason and time", async () => {
    const g = createReliabilityDemoGateway("normal"),
      data = await g.load(org, signal()),
      a = data.assessments.items[0];
    await g.decide(
      org,
      a.id,
      {
        status: "confirmed",
        reason: "Synthetic audit reason",
        expected_decision: null,
      },
      signal(),
    );
    const updated = await g.assessment(org, a.id, signal());
    render(
      <FinancialDecisionAudit gateway={g} orgId={org} detail={updated} demo />,
    );
    expect(
      await screen.findByText("Synthetic audit reason"),
    ).toBeInTheDocument();
    expect(screen.getByText(/browser memory only/)).toBeInTheDocument();
    expect(screen.getByText("Actor ID")).toBeInTheDocument();
  });
  it("does not treat an unrelated audit row as financial decision history", async () => {
    const g = createDemoGateway(),
      data = await g.load(org, signal());
    g.audit = async () => ({ items: [], total: 500, limit: 100, offset: 0 });
    render(
      <FinancialDecisionAudit
        gateway={g}
        orgId={org}
        detail={{
          ...data.assessments.items[0],
          decision_id: "00000000-0000-4000-8000-000000009999",
        }}
        demo={false}
      />,
    );
    expect(
      await screen.findByText(/not proof of missing database history/),
    ).toBeInTheDocument();
  });
  it("discards a late audit response when another tenant is selected", async () => {
    const g = createDemoGateway(),
      data = await g.load(org, signal());
    let oldSignal!: AbortSignal;
    let resolve!: (p: unknown) => void;
    g.audit = vi.fn((_, s) => {
      oldSignal = s;
      return new Promise((r) => {
        resolve = r;
      });
    }) as WorkspaceGateway["audit"];
    const a = {
      ...data.assessments.items[0],
      decision_id: "00000000-0000-4000-8000-000000009999",
    };
    const rendered = render(
      <FinancialDecisionAudit
        gateway={g}
        orgId={org}
        detail={a}
        demo={false}
      />,
    );
    const signalA = oldSignal;
    rendered.rerender(
      <FinancialDecisionAudit
        gateway={{
          ...g,
          audit: async () => ({ items: [], total: 0, limit: 100, offset: 0 }),
        }}
        orgId="other"
        detail={a}
        demo={false}
      />,
    );
    expect(signalA.aborted).toBe(true);
    await act(async () =>
      resolve({
        items: [{ detail: { reason: "Private old tenant" } }],
        total: 1,
      }),
    );
    await waitFor(() =>
      expect(screen.queryByText("Private old tenant")).not.toBeInTheDocument(),
    );
  });
});
