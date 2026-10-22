/** Explicit query-boundary fixtures, not authenticated SQL integration. */
import {
  act,
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ServerExceptionsQueue } from "@/components/server-exceptions-queue";
import { ProductConsole } from "@/components/product-console";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import { withSyntheticServerQuery } from "@/lib/product-demo-server-query";
import {
  liveWorkspaceGateway,
  type WorkspaceGateway,
} from "@/lib/product-workspace";
import { exceptionsPath, type ExceptionPage } from "@/lib/server-exceptions";
const org = demoUser.organizations[0].id,
  signal = () => new AbortController().signal;
const fixture = () =>
  withSyntheticServerQuery(withSyntheticExceptionContext(createDemoGateway()));
const props = (gateway: WorkspaceGateway) => ({
  gateway,
  org,
  reviewOnly: false,
  invoice: "",
  onOpen: vi.fn(),
  demo: true,
  refresh: 0,
});
async function page() {
  return fixture().queryExceptions!(org, {}, 2, null, signal());
}

describe("server query contract", () => {
  it("encodes criteria and cursor without leaking tokens or introducing tenant overrides", () => {
    const path = exceptionsPath(
      { q: "literal & %_", supplier: "DEMO", currency: "USD", current: false },
      20,
      "opaque-cursor",
    );
    const url = new URL(path, "http://fixture.test");
    expect(url.searchParams.get("q")).toBe("literal & %_");
    expect(url.searchParams.get("pagination")).toBe("cursor");
    expect(url.searchParams.has("current")).toBe(false);
    expect(url.searchParams.get("after")).toBe("opaque-cursor");
  });
  it("calls only the existing scoped endpoint and preserves the server page order", async () => {
    const result = await page(),
      fetcher = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValue(Response.json(result));
    try {
      expect(
        await liveWorkspaceGateway.queryExceptions!(
          org,
          { sort: "amount_high" },
          20,
          "opaque",
          signal(),
        ),
      ).toEqual(result);
      expect(fetcher).toHaveBeenCalledWith(
        expect.stringContaining(
          `/api/organizations/${org}/financial/evaluations?pagination=cursor&limit=20&sort=amount_high&after=opaque`,
        ),
        expect.objectContaining({ credentials: "same-origin", method: "GET" }),
      );
      expect(fetcher.mock.calls[0][1]?.headers).toBeUndefined();
    } finally {
      fetcher.mockRestore();
    }
  });
  it("loads reference context without preloading evaluations for the server queue", async () => {
    const original = await createDemoGateway().load(org, signal()),
      fetcher = vi
        .spyOn(globalThis, "fetch")
        .mockImplementation(async (path) =>
          Response.json(
            String(path).includes("summary")
              ? original.summary
              : String(path).includes("documents?")
                ? original.documents
                : original.sources,
          ),
        );
    try {
      const data = await liveWorkspaceGateway.loadContext!(org, signal());
      expect(data.assessments.items).toEqual([]);
      expect(fetcher).toHaveBeenCalledTimes(2);
      expect(
        fetcher.mock.calls.some(([url]) => String(url).includes("evaluations")),
      ).toBe(false);
    } finally {
      fetcher.mockRestore();
    }
  });
  it("surfaces the server concurrency restart message instead of a decision-form message", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json(
        {
          error: {
            code: "EXCEPTIONS_CHANGED",
            message: "Financial records changed; restart the query",
          },
        },
        { status: 409 },
      ),
    );
    try {
      await expect(
        liveWorkspaceGateway.queryExceptions!(org, {}, 20, "old", signal()),
      ).rejects.toMatchObject({
        status: 409,
        message: "Financial records changed; restart the query",
      });
    } finally {
      fetcher.mockRestore();
    }
  });
});

describe("interactive server-driven queue", () => {
  it("requests combined filters and restarts at the beginning after a criterion changes", async () => {
    const gateway = fixture(),
      query = vi.spyOn(gateway, "queryExceptions");
    render(<ServerExceptionsQueue {...props(gateway)} />);
    await screen.findByText("4 matching assessments");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText(/3–4 of 4/);
    fireEvent.change(screen.getByLabelText("Server currency"), {
      target: { value: "USD" },
    });
    fireEvent.change(screen.getByLabelText("Server supplier"), {
      target: { value: "AcmeCloud" },
    });
    fireEvent.change(screen.getByLabelText("Server sort"), {
      target: { value: "amount_high" },
    });
    await screen.findByText("2 matching assessments");
    expect(query).toHaveBeenLastCalledWith(
      org,
      expect.objectContaining({
        currency: "USD",
        supplier: "AcmeCloud",
        sort: "amount_high",
      }),
      2,
      null,
      expect.any(AbortSignal),
    );
    expect(
      screen.getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
  });
  it("displays authoritative counts separately and never resorts a returned page", async () => {
    const gateway = fixture(),
      result = await page();
    result.total = 257;
    result.items = [
      {
        ...result.items[0],
        id: "first",
        potential: "1.000001",
        invoice_filename: "FIRST.pdf",
      },
      {
        ...result.items[1],
        id: "second",
        potential: "99999999999999.123456",
        invoice_filename: "SECOND.pdf",
      },
    ];
    gateway.queryExceptions = vi.fn().mockResolvedValue(result);
    render(<ServerExceptionsQueue {...props(gateway)} />);
    await screen.findByText("257 matching assessments");
    expect(screen.getByRole("status")).toHaveTextContent(
      "2 loaded on this page",
    );
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("FIRST.pdf");
    expect(rows[2]).toHaveTextContent("SECOND.pdf");
    expect(
      screen.getByText("99,999,999,999,999.123456 EUR"),
    ).toBeInTheDocument();
  });
  it("aborts a stale filter request and suppresses its late rows and counts", async () => {
    const gateway = fixture(),
      fresh = await page();
    let resolve!: (page: ExceptionPage) => void, oldSignal!: AbortSignal;
    gateway.queryExceptions = vi.fn((_org, filters, _limit, _after, sig) =>
      filters.q
        ? Promise.resolve({
            ...fresh,
            total: 1,
            items: [{ ...fresh.items[0], invoice_filename: "CURRENT.pdf" }],
          })
        : new Promise<ExceptionPage>((r) => {
            resolve = r;
            oldSignal = sig;
          }),
    );
    render(<ServerExceptionsQueue {...props(gateway)} />);
    await waitFor(() =>
      expect(gateway.queryExceptions).toHaveBeenCalledTimes(1),
    );
    fireEvent.change(screen.getByLabelText("Search server records"), {
      target: { value: "current" },
    });
    await screen.findByText("CURRENT.pdf");
    expect(oldSignal.aborted).toBe(true);
    await act(async () =>
      resolve({
        ...fresh,
        total: 999,
        items: [{ ...fresh.items[0], invoice_filename: "STALE.pdf" }],
      }),
    );
    expect(screen.queryByText("STALE.pdf")).not.toBeInTheDocument();
    expect(
      screen.queryByText("999 matching assessments"),
    ).not.toBeInTheDocument();
  });
  it("suppresses an old organization response and never sends its cursor to another tenant", async () => {
    const gateway = fixture(),
      result = await page();
    let resolve!: (page: ExceptionPage) => void, oldSignal!: AbortSignal;
    const other = "00000000-0000-4000-8000-000000000003";
    gateway.queryExceptions = vi.fn((id, _filters, _limit, _after, sig) =>
      id === org
        ? new Promise<ExceptionPage>((r) => {
            resolve = r;
            oldSignal = sig;
          })
        : Promise.resolve({
            ...result,
            total: 0,
            items: [],
            has_more: false,
            next_cursor: null,
          }),
    );
    const view = render(<ServerExceptionsQueue {...props(gateway)} />);
    await waitFor(() =>
      expect(gateway.queryExceptions).toHaveBeenCalledTimes(1),
    );
    view.rerender(<ServerExceptionsQueue {...props(gateway)} org={other} />);
    await screen.findByText("No matching exceptions");
    expect(oldSignal.aborted).toBe(true);
    await act(async () => resolve(result));
    expect(
      screen.queryByText("4 matching assessments"),
    ).not.toBeInTheDocument();
    expect(gateway.queryExceptions).toHaveBeenLastCalledWith(
      other,
      expect.any(Object),
      2,
      null,
      expect.any(AbortSignal),
    );
  });
  it("retries the same read cursor after a network error, with no write or duplicate page", async () => {
    const gateway = fixture(),
      query = gateway.queryExceptions!,
      post = vi.spyOn(gateway, "decide");
    let failed = false;
    gateway.queryExceptions = vi.fn(
      async (
        ...args: Parameters<NonNullable<WorkspaceGateway["queryExceptions"]>>
      ) => {
        if (args[3] && !failed) {
          failed = true;
          throw Error("Synthetic page network failure");
        }
        return query(...args);
      },
    );
    render(<ServerExceptionsQueue {...props(gateway)} />);
    await screen.findByText("4 matching assessments");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Synthetic page network failure",
    );
    const cursor = (
      gateway.queryExceptions as ReturnType<typeof vi.fn>
    ).mock.calls.at(-1)![3];
    fireEvent.click(screen.getByRole("button", { name: "Retry this page" }));
    await screen.findByText(/3–4 of 4/);
    expect(gateway.queryExceptions).toHaveBeenLastCalledWith(
      org,
      expect.any(Object),
      2,
      cursor,
      expect.any(AbortSignal),
    );
    expect(screen.getAllByRole("row")).toHaveLength(3);
    expect(post).not.toHaveBeenCalled();
  });
  it("reports invalidated cursors and restarts after a concurrent decision", async () => {
    const gateway = fixture();
    render(<ServerExceptionsQueue {...props(gateway)} />);
    await screen.findByText("4 matching assessments");
    const a = (await gateway.load(org, signal())).assessments.items[0];
    await gateway.decide(
      org,
      a.id,
      {
        status: "confirmed",
        reason: "DEMO concurrent review",
        expected_decision: a.decision_id,
      },
      signal(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "cursor invalidated",
    );
    fireEvent.click(
      within(screen.getByRole("alert")).getByRole("button", {
        name: "Restart query",
      }),
    );
    await screen.findByText(/1–2 of 4/);
  });
  it("supports direct investigation of an assessment returned on a later page", async () => {
    const gateway = fixture();
    render(
      <ProductConsole
        user={demoUser}
        view="anomalies"
        gateway={gateway}
        demo
      />,
    );
    await screen.findByText("4 matching assessments");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText(/3–4 of 4/);
    fireEvent.click(
      screen.getByRole("button", {
        name: "Investigate 00000000-0000-4000-8000-000000001001",
      }),
    );
    await screen.findByRole("heading", { name: "Enterprise seats · October" });
    expect(
      screen.getByRole("link", { name: "Direct case link" }),
    ).toHaveAttribute(
      "href",
      `/demo/anomalies?org=${org}&assessment=00000000-0000-4000-8000-000000001001`,
    );
  });
  it("keeps unknown amount, missing association and an empty response explicit", async () => {
    const gateway = fixture();
    render(<ServerExceptionsQueue {...props(gateway)} />);
    await screen.findByText("Not assessed");
    expect(
      within(screen.getByRole("table")).getByText(
        "No unique association returned",
      ),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search server records"), {
      target: { value: "no-match" },
    });
    await screen.findByText("No matching exceptions");
    expect(screen.getByText("0 matching assessments")).toBeInTheDocument();
  });
});
