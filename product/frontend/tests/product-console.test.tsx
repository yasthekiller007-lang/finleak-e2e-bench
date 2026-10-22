import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductConsole } from "@/components/product-console";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { WorkspaceError, type WorkspaceData } from "@/lib/product-workspace";

const org = demoUser.organizations[0].id;
const signal = () => new AbortController().signal;

async function openFinding(gateway = createDemoGateway(), role = "owner") {
  const user = {
    ...demoUser,
    organizations: [{ ...demoUser.organizations[0], role: role as "owner" }],
  };
  render(<ProductConsole user={user} view="invoices" gateway={gateway} />);
  const filename = await screen.findByText("AcmeCloud_INV-2026-1042.pdf");
  fireEvent.click(
    within(filename.closest("tr")!).getByRole("button", {
      name: /View finding/,
    }),
  );
  await screen.findByRole("heading", { name: /Enterprise seats/ });
  return gateway;
}

describe("integrated product screens with controlled API-boundary fixtures", () => {
  it("shows separate financial currencies and labels recovery as unreported", async () => {
    render(
      <ProductConsole
        user={demoUser}
        view="dashboard"
        gateway={createDemoGateway()}
      />,
    );
    expect(await screen.findByText("12,480.00")).toBeInTheDocument();
    expect(screen.getByText("1,380.00")).toBeInTheDocument();
    expect(screen.getByText("Not reported here")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Explore findings/ }),
    ).toHaveAttribute("href", `/anomalies?org=${org}`);
    expect(
      screen.getByText(
        /Queue counts, documents and activity reflect loaded records only/,
      ),
    ).toBeInTheDocument();
  });
  it("follows an invoice into exact calculation, contract source, issued proof and human decision", async () => {
    const gateway = createDemoGateway();
    const decide = vi.spyOn(gateway, "decide");
    await openFinding(gateway);
    expect(screen.getByText("26,880.00 USD")).toBeInTheDocument();
    expect(screen.getByText("36,480.00 USD")).toBeInTheDocument();
    expect(
      screen.getByText("AcmeCloud_Master-Services-2026.pdf"),
    ).toBeInTheDocument();
    expect(await screen.findByText("COMPLETE")).toBeInTheDocument();
    const save = screen.getByRole("button", {
      name: "Record financial decision",
    });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason for decision"), {
      target: { value: "  Contract and invoice verified  " },
    });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(save);
    await screen.findByText(
      "Decision recorded. Historical calculations and evidence remain unchanged.",
    );
    expect(decide).toHaveBeenCalledWith(
      org,
      expect.any(String),
      {
        status: "confirmed",
        reason: "Contract and invoice verified",
        expected_decision: null,
      },
      expect.any(AbortSignal),
    );
    expect(screen.getAllByText("Confirmed").length).toBeGreaterThan(0);
    fireEvent.click(
      screen.getByRole("tab", { name: /Review & audit history/ }),
    );
    expect(
      await screen.findByText(/Current finding decision ID/),
    ).toHaveTextContent("not the decision’s actor or reason");
  });
  it.each(["analyst", "viewer"])(
    "keeps %s finding decisions read-only",
    async (role) => {
      await openFinding(createDemoGateway(), role);
      expect(
        screen.queryByRole("button", { name: "Record financial decision" }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(/An owner or administrator must finalize/),
      ).toBeInTheDocument();
    },
  );
  it("permits an administrator to use the authorized decision form", async () => {
    await openFinding(createDemoGateway(), "admin");
    expect(screen.getByLabelText("Finding decision")).toBeInTheDocument();
  });
  it("blocks a stale assessment and labels its historical amount", async () => {
    const gateway = createDemoGateway(),
      read = gateway.assessment;
    gateway.assessment = async (...args) => ({
      ...(await read(...args)),
      stale: true,
    });
    await openFinding(gateway);
    expect(
      screen.getByText(/This is a historical assessment/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Record financial decision" }),
    ).not.toBeInTheDocument();
  });
  it("requires a refresh after a concurrent financial review, with no false success", async () => {
    const gateway = createDemoGateway();
    gateway.decide = vi
      .fn()
      .mockRejectedValue(
        new WorkspaceError(
          "This record changed. Refresh the assessment before making another decision.",
          409,
        ),
      );
    await openFinding(gateway);
    fireEvent.change(screen.getByLabelText("Reason for decision"), {
      target: { value: "Evidence reviewed" },
    });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(
      screen.getByRole("button", { name: "Record financial decision" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Refresh the assessment",
    );
    expect(screen.queryByText(/Decision recorded/)).not.toBeInTheDocument();
  });
  it("searches the loaded invoice register and provides an honest empty state", async () => {
    render(
      <ProductConsole
        user={demoUser}
        view="invoices"
        gateway={createDemoGateway()}
      />,
    );
    await screen.findByText("AcmeCloud_INV-2026-1042.pdf");
    fireEvent.change(screen.getByLabelText("Search loaded records"), {
      target: { value: "not-present" },
    });
    expect(screen.getByText("No matching documents")).toBeInTheDocument();
    expect(
      screen.getByText(/an unlinked document is not a clean bill of health/),
    ).toBeInTheDocument();
  });
  it("limits an invoice deep link to its actual source relationship", async () => {
    const gateway = createDemoGateway();
    const data = await gateway.load(org, signal());
    render(
      <ProductConsole
        user={demoUser}
        view="anomalies"
        gateway={gateway}
        initialInvoice={data.assessments.items[0].invoice_source_id}
      />,
    );
    await screen.findByRole("button", { name: "AcmeCloud_INV-2026-1042.pdf" });
    expect(
      screen.queryByRole("button", { name: "Atlas_INV-2026-0318.pdf" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Clear invoice filter" }),
    ).toHaveAttribute("href", `/anomalies?org=${org}`);
  });
  it("does not turn missing financial evidence into zero or a reviewable monetary finding", async () => {
    const gateway = createDemoGateway();
    const data = await gateway.load(org, signal());
    render(
      <ProductConsole
        user={demoUser}
        view="review"
        gateway={gateway}
        initialAssessment={data.assessments.items[3].id}
      />,
    );
    await screen.findByRole("heading", {
      name: "Additional storage · October",
    });
    expect(screen.getAllByText("Not assessed")).toHaveLength(3);
    expect(
      screen.getByText(/an unknown amount is not zero/),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Finding decision")).not.toBeInTheDocument();
  });
  it("paginates using the unfiltered server document window", async () => {
    const gateway = createDemoGateway(),
      read = gateway.load;
    gateway.load = async (...args) => {
      const data = await read(...args);
      return { ...data, documents: { ...data.documents, total: 101 } };
    };
    const more = vi.spyOn(gateway, "documents");
    render(
      <ProductConsole user={demoUser} view="invoices" gateway={gateway} />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Load more records" }),
    );
    expect(more).toHaveBeenCalledWith(org, 100, expect.any(AbortSignal));
    await screen.findByText(/8 \/ 8 source documents loaded/);
    expect(
      screen.queryByRole("button", { name: "Load more records" }),
    ).not.toBeInTheDocument();
  });
  it("aborts old tenant reads and ignores a late response after an organization switch", async () => {
    const gateway = createDemoGateway(),
      original = await gateway.load(org, signal());
    let resolveOld!: (data: WorkspaceData) => void;
    let oldSignal!: AbortSignal;
    const other = "00000000-0000-4000-8000-000000000003";
    const user = {
      ...demoUser,
      organizations: [
        ...demoUser.organizations,
        { id: other, name: "Other organization", role: "viewer" as const },
      ],
    };
    const empty = {
      ...original,
      summary: {
        ...original.summary,
        potential_by_currency: {},
        potential_by_rule: {},
      },
      documents: { ...original.documents, items: [], total: 0 },
      assessments: { ...original.assessments, items: [], total: 0 },
      sources: { ...original.sources, items: [], total: 0 },
    };
    gateway.load = vi.fn((id, sig) =>
      id === org
        ? new Promise<WorkspaceData>((resolve) => {
            resolveOld = resolve;
            oldSignal = sig;
          })
        : Promise.resolve(empty),
    );
    render(<ProductConsole user={user} view="dashboard" gateway={gateway} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading your organization",
    );
    fireEvent.change(screen.getByLabelText("Active organization"), {
      target: { value: other },
    });
    await screen.findByText("No current monetary findings");
    expect(oldSignal.aborted).toBe(true);
    await act(async () => resolveOld(original));
    expect(screen.queryByText("12,480.00")).not.toBeInTheDocument();
  });
  it("shows a service error, then retries rather than substituting demo data", async () => {
    const gateway = createDemoGateway(),
      read = gateway.load;
    gateway.load = vi
      .fn()
      .mockRejectedValueOnce(new Error("Session expired"))
      .mockImplementation(read);
    render(
      <ProductConsole user={demoUser} view="dashboard" gateway={gateway} />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Session expired",
    );
    expect(screen.queryByText("12,480.00")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("12,480.00");
  });
  it("does not call the gateway without an authorized organization", () => {
    const gateway = createDemoGateway();
    const load = vi.spyOn(gateway, "load");
    render(
      <ProductConsole
        user={{ ...demoUser, organizations: [] }}
        view="dashboard"
        gateway={gateway}
      />,
    );
    expect(screen.getByText("Your workspace is waiting")).toBeInTheDocument();
    expect(load).not.toHaveBeenCalled();
  });
  it("marks demo records as synthetic and keeps its navigation inside the demo", async () => {
    render(
      <ProductConsole
        user={demoUser}
        view="dashboard"
        gateway={createDemoGateway()}
        demo
      />,
    );
    expect(
      within(screen.getByRole("note")).getByText(/No live API requests/),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("link", { name: /Explore findings/ }),
    ).toHaveAttribute("href", `/demo/anomalies?org=${org}`);
    expect(
      screen.queryByRole("link", { name: /Import documents/ }),
    ).not.toBeInTheDocument();
  });
});
