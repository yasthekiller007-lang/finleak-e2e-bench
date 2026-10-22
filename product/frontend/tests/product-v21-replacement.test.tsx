/** Explicit synthetic gateways/component contracts. No native OIDC/PostgreSQL proof. */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PersonalSavedViews } from "@/components/personal-saved-views";
import { SavedViewCriteriaDiff } from "@/components/saved-view-criteria-diff";
import { ExceptionViewWorkspace } from "@/components/exception-view-workspace";
import { compareSavedCriteria } from "@/lib/saved-view-diff";
import {
  savedDefinition,
  SavedViewsError,
  type SavedDefinition,
  type SavedView,
} from "@/lib/saved-views";
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticSavedViews } from "@/lib/product-demo-saved-views";
import { withSyntheticExceptionContext } from "@/lib/product-demo-exceptions";
import { withSyntheticServerQuery } from "@/lib/product-demo-server-query";
import { withSyntheticBusinessFacets } from "@/lib/product-demo-business-facets";
import { viewPath } from "@/lib/exception-view-url";
const org = demoUser.organizations[0].id,
  owner = demoUser.id,
  idA = "aaaaaaaa-0000-4000-8000-000000000001",
  idB = "aaaaaaaa-0000-4000-8000-000000000002";
const def = (criteria: SavedDefinition["criteria"] = { currency: "USD" }) =>
  savedDefinition(
    { view_type: "anomalies", format_version: 1, criteria, page_size: 2 },
    true,
  );
const signal = () => new AbortController().signal;
const panel = () =>
  within(screen.getByRole("region", { name: "My saved views" }));
const diff = () =>
  within(screen.getByRole("region", { name: "Review saved view changes" }));
afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});
async function setup(saved = def(), target = def({ currency: "EUR" })) {
  const workspace = withSyntheticSavedViews(createDemoGateway(), false),
    gateway = workspace.savedViews!;
  const row = await gateway.create(
    org,
    owner,
    "CFO watchlist",
    saved,
    signal(),
  );
  let current: SavedDefinition | null = target,
    epoch = 0;
  const props = {
    gateway,
    org,
    owner,
    view: "anomalies" as const,
    demo: true,
    authorized: true,
    canSave: true,
    getCurrent: () => current,
    getCriteriaVersion: () => epoch,
    onOpen: vi.fn(() => true),
  };
  const r = render(<PersonalSavedViews {...props} criteriaVersion={epoch} />);
  await screen.findByRole("button", {
    name: "Manage saved view CFO watchlist",
  });
  fireEvent.click(
    panel().getByRole("button", { name: "Manage saved view CFO watchlist" }),
  );
  await screen.findByRole("textbox", { name: "Rename personal view" });
  const update = vi.spyOn(gateway, "update"),
    get = vi.spyOn(gateway, "get");
  const setCurrent = (
    next: SavedDefinition | null,
    canSave = Boolean(next),
  ) => {
    current = next;
    epoch++;
    r.rerender(
      <PersonalSavedViews
        {...props}
        criteriaVersion={epoch}
        canSave={canSave}
      />,
    );
  };
  const reprops = (patch: Partial<typeof props>) =>
    r.rerender(
      <PersonalSavedViews {...props} criteriaVersion={epoch} {...patch} />,
    );
  return {
    gateway,
    workspace,
    row,
    update,
    get,
    ...r,
    setCurrent,
    reprops,
    props,
  };
}
async function review() {
  fireEvent.click(
    panel().getByRole("button", { name: "Update saved criteria" }),
  );
  await screen.findByRole("region", { name: "Review saved view changes" });
}
it("re-reads before displaying a comparison and performs no write on opening", async () => {
  const f = await setup();
  await review();
  expect(f.get).toHaveBeenCalledTimes(1);
  expect(f.update).not.toHaveBeenCalled();
  expect(
    diff().getByRole("heading", { name: "Review saved view changes" }),
  ).toHaveFocus();
  expect(
    diff().getByRole("table", { name: "Changed criteria comparison" }),
  ).toHaveTextContent("USD");
  expect(
    diff().getByRole("table", { name: "Changed criteria comparison" }),
  ).toHaveTextContent("EUR");
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeEnabled();
});
it("keeps unchanged fields accessible through a native details element", async () => {
  await setup();
  await review();
  const summary = diff().getByText("Unchanged criteria (14)");
  expect(summary.tagName).toBe("SUMMARY");
  expect(summary.closest("details")).toBeInTheDocument();
  expect(diff().getByRole("button", { name: "Cancel" })).toBeEnabled();
});
it("does not increment versions or call PATCH when there are no differences", async () => {
  const f = await setup(def(), def());
  await review();
  expect(diff().getByText("No changes to save")).toBeInTheDocument();
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
  fireEvent.click(diff().getByRole("button", { name: "Confirm replacement" }));
  expect(f.update).not.toHaveBeenCalled();
  expect((await f.gateway.get(org, owner, f.row.id, signal())).revision).toBe(
    1,
  );
});
it("cancels without mutation and returns keyboard focus to the update action", async () => {
  const f = await setup();
  await review();
  fireEvent.click(diff().getByRole("button", { name: "Cancel" }));
  expect(
    screen.queryByRole("region", { name: "Review saved view changes" }),
  ).not.toBeInTheDocument();
  expect(
    panel().getByRole("button", { name: "Update saved criteria" }),
  ).toHaveFocus();
  expect(f.update).not.toHaveBeenCalled();
});
it("sends exactly the displayed replacement and the version re-read from the API", async () => {
  const f = await setup();
  await review();
  fireEvent.click(diff().getByRole("button", { name: "Confirm replacement" }));
  await screen.findByText("Synthetic criteria updated in memory only.");
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(f.update.mock.calls[0][3]).toBe(1);
  expect(f.update.mock.calls[0][4]).toMatchObject({
    definition: { criteria: { currency: "EUR" } },
  });
  expect(f.update.mock.calls[0][4]).not.toHaveProperty("name");
  expect((await f.gateway.get(org, owner, f.row.id, signal())).revision).toBe(
    2,
  );
});
it("returns focus to the persistent heading when cancellation occurs during a pending criteria read", async () => {
  const f = await setup();
  await review();
  f.setCurrent(null, false);
  fireEvent.click(diff().getByRole("button", { name: "Cancel" }));
  expect(
    panel().getByRole("heading", { name: "My saved views" }),
  ).toHaveFocus();
  expect(f.update).not.toHaveBeenCalled();
});
it("keeps rename name-only and separately reviews replacement against the new revision", async () => {
  const f = await setup();
  fireEvent.change(
    panel().getByRole("textbox", { name: "Rename personal view" }),
    {
      target: { value: "Renamed watchlist" },
    },
  );
  fireEvent.click(panel().getByRole("button", { name: "Rename view" }));
  await waitFor(() => expect(f.update).toHaveBeenCalledTimes(1));
  expect(f.update.mock.calls[0][4]).toEqual({ name: "Renamed watchlist" });
  await waitFor(() =>
    expect(
      panel().getByRole("button", { name: "Update saved criteria" }),
    ).toBeEnabled(),
  );
  await review();
  expect(diff().getByText(/Re-read version 2/)).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
  fireEvent.click(diff().getByRole("button", { name: "Confirm replacement" }));
  await screen.findByText("Synthetic criteria updated in memory only.");
  expect(f.update).toHaveBeenCalledTimes(2);
  expect(f.update.mock.calls[1][3]).toBe(2);
  expect(f.update.mock.calls[1][4]).not.toHaveProperty("name");
  expect(f.update.mock.calls[1][4]).toHaveProperty("definition");
});
it("shows a changed saved version before any replacement and uses its fresh revision", async () => {
  const f = await setup();
  const original = f.update.getMockImplementation();
  await f.gateway.update(
    org,
    owner,
    f.row.id,
    1,
    { name: "Changed in another tab" },
    signal(),
  );
  f.update.mockClear();
  await review();
  expect(diff().getByText(/changed from version 1 to 2/)).toBeInTheDocument();
  expect(diff().getByText("Changed in another tab")).toBeInTheDocument();
  expect(f.update).not.toHaveBeenCalled();
  fireEvent.click(diff().getByRole("button", { name: "Confirm replacement" }));
  await screen.findByText("Synthetic criteria updated in memory only.");
  expect(f.update.mock.calls[0][3]).toBe(2);
  void original;
});
it("invalidates after a criterion changes and stays invalid when it returns to the old value", async () => {
  const f = await setup();
  await review();
  f.setCurrent(def({ currency: "GBP" }));
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
  f.setCurrent(def({ currency: "EUR" }));
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
  fireEvent.click(diff().getByRole("button", { name: "Review changes again" }));
  await waitFor(() =>
    expect(
      diff().getByRole("button", { name: "Confirm replacement" }),
    ).toBeEnabled(),
  );
  expect(f.get).toHaveBeenCalledTimes(2);
  expect(f.update).not.toHaveBeenCalled();
});
it("refuses a changed current definition even if a caller forgets to increment its UI epoch", async () => {
  const f = await setup();
  await review();
  f.reprops({ getCurrent: () => def({ currency: "GBP" }) });
  fireEvent.click(diff().getByRole("button", { name: "Confirm replacement" }));
  expect(diff().getByRole("alert")).toHaveTextContent("no longer match");
  expect(f.update).not.toHaveBeenCalled();
});
it("refuses pending or failed current reads and never saves the last old snapshot", async () => {
  const f = await setup();
  await review();
  f.setCurrent(null, false);
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
  expect(f.update).not.toHaveBeenCalled();
});
it("invalidates a comparison when criteria change while its saved-view GET is pending", async () => {
  const f = await setup();
  let resolve!: (r: SavedView) => void;
  f.get.mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  fireEvent.click(
    panel().getByRole("button", { name: "Update saved criteria" }),
  );
  expect(
    screen.queryByRole("button", { name: "Confirm replacement" }),
  ).not.toBeInTheDocument();
  f.setCurrent(def({ currency: "GBP" }));
  await act(async () => resolve(f.row));
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
  expect(diff().getByRole("alert")).toHaveTextContent("changed while");
  expect(f.update).not.toHaveBeenCalled();
});
it.each(["organization", "user", "membership"])(
  "cancels pending comparison reads on %s changes without showing old private data",
  async (change) => {
    const f = await setup();
    let resolve!: (r: SavedView) => void;
    let pending: AbortSignal | undefined;
    f.get.mockImplementationOnce((_o, _u, _i, s) => {
      pending = s;
      return new Promise((r) => {
        resolve = r;
      });
    });
    fireEvent.click(
      panel().getByRole("button", { name: "Update saved criteria" }),
    );
    f.reprops(
      change === "organization"
        ? { org: idA }
        : change === "user"
          ? { owner: idA }
          : { authorized: false },
    );
    expect(pending!.aborted).toBe(true);
    await act(async () => resolve(f.row));
    expect(
      screen.queryByRole("region", { name: "Review saved view changes" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/CFO watchlist ·/)).not.toBeInTheDocument();
    expect(f.update).not.toHaveBeenCalled();
  },
);
it("keeps the proposed criteria and name draft after 409; re-read builds a new comparison without replay", async () => {
  const f = await setup();
  fireEvent.change(
    panel().getByRole("textbox", { name: "Rename personal view" }),
    { target: { value: "My retained name draft" } },
  );
  await review();
  await f.gateway.update(
    org,
    owner,
    f.row.id,
    1,
    { name: "Another tab" },
    signal(),
  );
  f.update.mockClear();
  fireEvent.click(diff().getByRole("button", { name: "Confirm replacement" }));
  await waitFor(() =>
    expect(diff().getByRole("alert")).toHaveTextContent("Version conflict"),
  );
  expect(
    panel().getByRole("textbox", { name: "Rename personal view" }),
  ).toHaveValue("My retained name draft");
  expect(
    diff().getByRole("table", { name: "Changed criteria comparison" }),
  ).toHaveTextContent("EUR");
  expect(f.update).toHaveBeenCalledTimes(1);
  fireEvent.click(diff().getByRole("button", { name: "Review changes again" }));
  await waitFor(() =>
    expect(diff().getByText(/Re-read version 2/)).toBeInTheDocument(),
  );
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeEnabled();
});
it("serializes rapid confirmations and waits for an authoritative matching response", async () => {
  const f = await setup();
  let release!: () => void;
  const original = f.gateway.update.bind(f.gateway);
  f.update.mockRestore();
  const update = vi
    .spyOn(f.gateway, "update")
    .mockImplementation(async (...args) => {
      const result = await original(...args);
      await new Promise<void>((r) => {
        release = r;
      });
      return result;
    });
  await review();
  const button = diff().getByRole("button", { name: "Confirm replacement" });
  act(() => {
    fireEvent.click(button);
    fireEvent.click(button);
  });
  await waitFor(() => expect(release).toBeDefined());
  expect(update).toHaveBeenCalledTimes(1);
  expect(
    screen.queryByText("Synthetic criteria updated in memory only."),
  ).not.toBeInTheDocument();
  await act(async () => release());
  expect(
    screen.getByText("Synthetic criteria updated in memory only."),
  ).toBeInTheDocument();
});
it("reconciles an uncertain write by explicit reading and detects no changes rather than replaying", async () => {
  const f = await setup();
  const original = f.gateway.update.bind(f.gateway);
  f.update.mockRestore();
  const update = vi
    .spyOn(f.gateway, "update")
    .mockImplementation(async (...args) => {
      await original(...args);
      throw Error("Synthetic response lost; outcome unknown");
    });
  await review();
  fireEvent.click(diff().getByRole("button", { name: "Confirm replacement" }));
  await waitFor(() =>
    expect(diff().getByRole("alert")).toHaveTextContent(
      "outcome is unconfirmed",
    ),
  );
  expect(
    screen.queryByText("Synthetic criteria updated in memory only."),
  ).not.toBeInTheDocument();
  expect(update).toHaveBeenCalledTimes(1);
  fireEvent.click(
    panel().getByRole("button", { name: "Reload personal views" }),
  );
  await waitFor(() =>
    expect(
      panel().getByRole("button", { name: "Update saved criteria" }),
    ).toBeEnabled(),
  );
  fireEvent.click(diff().getByRole("button", { name: "Review changes again" }));
  await screen.findByText("No changes to save");
  expect(update).toHaveBeenCalledTimes(1);
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
});
it("does not present a mismatched response as replacement success", async () => {
  const f = await setup();
  f.update.mockResolvedValue({ ...f.row, revision: 2 });
  await review();
  fireEvent.click(diff().getByRole("button", { name: "Confirm replacement" }));
  await waitFor(() =>
    expect(diff().getByRole("alert")).toHaveTextContent(
      "outcome is unconfirmed",
    ),
  );
  expect(
    screen.queryByText("Synthetic criteria updated in memory only."),
  ).not.toBeInTheDocument();
});
it("handles a failed saved-view read with an explicit retry and no PATCH", async () => {
  const f = await setup();
  f.get.mockRejectedValueOnce(
    new SavedViewsError("Synthetic read unavailable", 503),
  );
  fireEvent.click(
    panel().getByRole("button", { name: "Update saved criteria" }),
  );
  await screen.findByText("Synthetic read unavailable");
  expect(f.update).not.toHaveBeenCalled();
  fireEvent.click(
    panel().getByRole("button", { name: "Review changes again" }),
  );
  await screen.findByRole("region", { name: "Review saved view changes" });
  expect(f.get).toHaveBeenCalledTimes(2);
});
it("refuses a returned record from another owner without exposing its private name", async () => {
  const f = await setup();
  f.get.mockResolvedValue({
    ...f.row,
    user_id: idA,
    name: "Other private view",
  });
  fireEvent.click(
    panel().getByRole("button", { name: "Update saved criteria" }),
  );
  await screen.findByText(/Unsupported personal view/);
  expect(screen.queryByText("Other private view")).not.toBeInTheDocument();
  expect(f.update).not.toHaveBeenCalled();
});
it("distinguishes homonymous sources without rendering raw UUIDs or substituting missing labels", () => {
  const comparison = compareSavedCriteria(
    { ...def({ invoice_source_id: idA }) },
    { ...def({ invoice_source_id: idB }) },
    true,
  );
  const { container } = render(
    <SavedViewCriteriaDiff
      name="Sources"
      revision={1}
      comparison={comparison}
      valid
      busy={false}
      labels={{
        organization_id: org,
        user_id: owner,
        values: {
          [`invoice_source_id:${idA}`]: "Same.pdf",
          [`invoice_source_id:${idB}`]: "Same.pdf",
        },
      }}
      demo
      onConfirm={() => {}}
      onCancel={() => {}}
      onReview={() => {}}
    />,
  );
  expect(screen.getAllByText("Same.pdf")).toHaveLength(2);
  expect(screen.getByText(/Different source identity/)).toBeInTheDocument();
  expect(container.textContent).not.toContain(idA);
  expect(container.textContent).not.toContain(idB);
});
it("uses explicit unavailable labels and never exposes document ids or financial fields", () => {
  const comparison = compareSavedCriteria(
    def({ contract_source_id: idA }),
    def({ contract_source_id: idB }),
    true,
  );
  const { container } = render(
    <SavedViewCriteriaDiff
      name="Missing labels"
      revision={1}
      comparison={comparison}
      valid
      busy={false}
      demo
      onConfirm={() => {}}
      onCancel={() => {}}
      onReview={() => {}}
    />,
  );
  expect(
    screen.getAllByText("Selected contract label unavailable"),
  ).toHaveLength(2);
  expect(container.textContent).not.toMatch(
    new RegExp(`${idA}|${idB}|9,600|recovered|Idempotency-Key|Bearer|after=`),
  );
});
it("uses the real queue guard for URL coherence and invalidates even batched edits returning to the original filter", async () => {
  const gateway = withSyntheticSavedViews(
    withSyntheticBusinessFacets(
      withSyntheticServerQuery(
        withSyntheticExceptionContext(createDemoGateway()),
      ),
    ),
    false,
  );
  await gateway.savedViews!.create(
    org,
    owner,
    "CFO watchlist",
    def({ currency: "USD" }),
    signal(),
  );
  window.history.replaceState(
    {},
    "",
    viewPath(org, { currency: "EUR" }, 2, "anomalies", true),
  );
  render(
    <ExceptionViewWorkspace
      user={demoUser}
      view="anomalies"
      demo
      gateway={gateway}
    />,
  );
  await waitFor(() =>
    expect(
      panel().getByRole("button", { name: "Save current view" }),
    ).toBeEnabled(),
  );
  fireEvent.click(
    panel().getByRole("button", { name: "Manage saved view CFO watchlist" }),
  );
  await screen.findByRole("textbox", { name: "Rename personal view" });
  await review();
  const input = screen.getByRole("textbox", { name: "Server currency" });
  act(() => {
    fireEvent.change(input, { target: { value: "GBP" } });
    fireEvent.change(input, { target: { value: "EUR" } });
  });
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
  await waitFor(() =>
    expect(
      panel().getByRole("button", { name: "Save current view" }),
    ).toBeEnabled(),
  );
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
});
