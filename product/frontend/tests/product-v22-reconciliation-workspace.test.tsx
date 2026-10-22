/** Explicit synthetic gateways and deferred transport doubles; not native OIDC/PostgreSQL. */
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
import { createDemoGateway, demoUser } from "@/lib/product-demo";
import { withSyntheticSavedViews } from "@/lib/product-demo-saved-views";
import {
  savedDefinition,
  SavedViewsError,
  type SavedDefinition,
  type SavedView,
} from "@/lib/saved-views";
const org = demoUser.organizations[0].id,
  owner = demoUser.id;
const definition = (currency: string) =>
  savedDefinition({
    view_type: "anomalies",
    format_version: 1,
    criteria: { currency },
    page_size: 20,
  });
const signal = () => new AbortController().signal;
const panel = () =>
  within(screen.getByRole("region", { name: "My saved views" }));
const summary = () =>
  within(screen.getByRole("region", { name: "Saved view reconciliation" }));
const diff = () =>
  within(screen.getByRole("region", { name: "Review saved view changes" }));
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});
async function setup() {
  const gateway = withSyntheticSavedViews(
    createDemoGateway(),
    false,
  ).savedViews!;
  const row = await gateway.create(
    org,
    owner,
    "CFO watchlist",
    definition("USD"),
    signal(),
  );
  const originalUpdate = gateway.update.bind(gateway),
    originalGet = gateway.get.bind(gateway);
  const get = vi.spyOn(gateway, "get"),
    update = vi.spyOn(gateway, "update"),
    remove = vi.spyOn(gateway, "remove");
  const props = {
    gateway,
    org,
    owner,
    view: "anomalies" as const,
    demo: true,
    authorized: true,
    canSave: true,
    getCurrent: (): SavedDefinition | null => definition("EUR"),
    onOpen: vi.fn(() => true),
  };
  const rendered = render(<PersonalSavedViews {...props} />);
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Manage saved view CFO watchlist",
    }),
  );
  await screen.findByRole("textbox", { name: "Rename personal view" });
  get.mockClear();
  return {
    gateway,
    row,
    get,
    update,
    remove,
    originalUpdate,
    originalGet,
    props,
    rendered,
  };
}
type Setup = Awaited<ReturnType<typeof setup>>;
async function lose(
  f: Setup,
  recorded = true,
  error: Error = new TypeError("Synthetic connection interrupted"),
) {
  f.update.mockImplementationOnce(async (...args) => {
    if (recorded) await f.originalUpdate(...args);
    throw error;
  });
  fireEvent.click(
    panel().getByRole("button", { name: "Update saved criteria" }),
  );
  await screen.findByRole("region", { name: "Review saved view changes" });
  fireEvent.click(diff().getByRole("button", { name: "Confirm replacement" }));
  await screen.findByRole("region", { name: "Saved view reconciliation" });
}
async function check() {
  fireEvent.click(
    summary().getByRole("button", { name: "Check saved view state" }),
  );
  await waitFor(() =>
    expect(
      summary().getByRole("button", { name: "Check saved view state" }),
    ).toBeEnabled(),
  );
}
it("retains an uncertain attempt in memory, does no automatic read/write and focuses its summary", async () => {
  const f = await setup();
  await lose(f);
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(f.get).toHaveBeenCalledTimes(1);
  expect(
    summary().getByText(/UI correlation only; not a server transaction ID/),
  ).toBeInTheDocument();
  expect(summary().getByRole("heading")).toHaveFocus();
  expect(
    summary().getByText(/No reconciliation read has completed/),
  ).toBeInTheDocument();
  expect(
    screen.queryByText("Synthetic criteria updated in memory only."),
  ).not.toBeInTheDocument();
});
it("re-reads the exact authorized view and observes the proposal without attributing the transaction", async () => {
  const f = await setup();
  await lose(f);
  await check();
  expect(f.get).toHaveBeenLastCalledWith(
    org,
    owner,
    f.row.id,
    expect.any(AbortSignal),
  );
  expect(
    summary().getByText("Proposed criteria found in the saved view."),
  ).toBeInTheDocument();
  expect(summary().getByText(/Observed version 2/)).toBeInTheDocument();
  expect(
    summary().getByText(/does not prove that this particular attempt/),
  ).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(f.remove).not.toHaveBeenCalled();
});
it("observes previous state at unchanged revision without declaring write failure", async () => {
  const f = await setup();
  await lose(f, false, new DOMException("Synthetic timeout", "TimeoutError"));
  await check();
  expect(
    summary().getByText(
      "Previous criteria are still recorded as of the latest read.",
    ),
  ).toBeInTheDocument();
  expect(summary().getByText(/Observed version 1/)).toBeInTheDocument();
  expect(
    summary().getByText(/not proof that the write failed/),
  ).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("reports later divergent state without overwriting it", async () => {
  const f = await setup();
  await lose(f);
  await f.originalUpdate(
    org,
    owner,
    f.row.id,
    2,
    { definition: definition("GBP") },
    signal(),
  );
  await check();
  expect(
    summary().getByText("The saved view differs from both compared states."),
  ).toBeInTheDocument();
  expect(summary().getByText(/Observed version 3/)).toBeInTheDocument();
  expect(
    (await f.originalGet(org, owner, f.row.id, signal())).criteria.currency,
  ).toBe("GBP");
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("requires a new comparison after 409 and retains the current proposal and name draft", async () => {
  const f = await setup();
  fireEvent.change(
    panel().getByRole("textbox", { name: "Rename personal view" }),
    { target: { value: "Retained draft" } },
  );
  await f.originalUpdate(
    org,
    owner,
    f.row.id,
    1,
    { name: "Other tab" },
    signal(),
  );
  // The fresh comparison sees revision 2; the PATCH is explicitly rejected at the boundary.
  await lose(f, false, new SavedViewsError("Synthetic conflict", 409));
  await check();
  expect(
    panel().getByRole("textbox", { name: "Rename personal view" }),
  ).toHaveValue("Retained draft");
  expect(
    summary().getByText(/returned a version conflict/),
  ).toBeInTheDocument();
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
  fireEvent.click(
    summary().getByRole("button", { name: "Review changes again" }),
  );
  await waitFor(() =>
    expect(
      diff().getByRole("button", { name: "Confirm replacement" }),
    ).toBeEnabled(),
  );
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(diff().getByText(/Re-read version 2/)).toBeInTheDocument();
});
it("freshly reviews an already recorded proposal as no changes and never resubmits", async () => {
  const f = await setup();
  await lose(f);
  await check();
  fireEvent.click(
    summary().getByRole("button", { name: "Review changes again" }),
  );
  await screen.findByText("No changes to save");
  expect(
    diff().getByRole("button", { name: "Confirm replacement" }),
  ).toBeDisabled();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it.each([503, 404])(
  "keeps the outcome unknown on read HTTP %s and permits an explicit read retry",
  async (status) => {
    const f = await setup();
    await lose(f);
    f.get.mockRejectedValueOnce(
      new SavedViewsError("Private error detail must not be copied", status),
    );
    await check();
    expect(
      summary().getByText("Unable to determine the saved state."),
    ).toBeInTheDocument();
    expect(
      summary().getByText(/does not establish write failure/),
    ).toBeInTheDocument();
    expect(
      summary().getByRole("button", { name: "Review changes again" }),
    ).toBeDisabled();
    expect(
      diff().getByRole("button", { name: "Review changes again" }),
    ).toBeDisabled();
    expect(screen.queryByText(/Private error detail/)).not.toBeInTheDocument();
    await check();
    expect(
      summary().getByText("Proposed criteria found in the saved view."),
    ).toBeInTheDocument();
    expect(f.update).toHaveBeenCalledTimes(1);
  },
);
it.each([401, 403])(
  "purges private context and stops further reconciliation on read HTTP %s",
  async (status) => {
    const f = await setup();
    await lose(f);
    f.get.mockRejectedValueOnce(
      new SavedViewsError("Sensitive upstream name", status),
    );
    fireEvent.click(
      summary().getByRole("button", { name: "Check saved view state" }),
    );
    await screen.findByText(/private view context cleared/);
    expect(panel().queryByText(/CFO watchlist/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Saved view reconciliation" }),
    ).not.toBeInTheDocument();
    expect(
      panel().getByRole("button", { name: "Reload personal views" }),
    ).toBeDisabled();
    expect(f.update).toHaveBeenCalledTimes(1);
  },
);
it.each([
  { user_id: "bbbbbbbb-0000-4000-8000-000000000001" },
  { organization_id: "bbbbbbbb-0000-4000-8000-000000000001" },
  { id: "bbbbbbbb-0000-4000-8000-000000000001" },
  { revision: 0 },
  { format_version: 2 },
  { criteria: { token: "SECRET_SENTINEL" } },
])(
  "rejects unverified reads %j without exposing their values",
  async (patch) => {
    const f = await setup();
    await lose(f);
    f.get.mockResolvedValueOnce({
      ...f.row,
      ...definition("EUR"),
      revision: 2,
      ...patch,
      name: "Other protected name",
    } as SavedView);
    await check();
    expect(
      summary().getByText("Unable to determine the saved state."),
    ).toBeInTheDocument();
    expect(
      panel().queryByText(/Other protected name|SECRET_SENTINEL/),
    ).not.toBeInTheDocument();
    expect(f.update).toHaveBeenCalledTimes(1);
  },
);
it("bounds a hung read, permits another read and ignores a late success from the timed-out request", async () => {
  const f = await setup();
  await lose(f);
  let late!: (r: SavedView) => void;
  f.get.mockImplementationOnce(
    () =>
      new Promise((r) => {
        late = r;
      }),
  );
  vi.useFakeTimers();
  fireEvent.click(
    summary().getByRole("button", { name: "Check saved view state" }),
  );
  await act(async () => {
    vi.advanceTimersByTime(30000);
  });
  expect(
    summary().getByText("Unable to determine the saved state."),
  ).toBeInTheDocument();
  expect(summary().getByText(/timed out/)).toBeInTheDocument();
  vi.useRealTimers();
  f.get.mockResolvedValueOnce({ ...f.row, ...definition("GBP"), revision: 3 });
  await check();
  await act(async () => late({ ...f.row, ...definition("EUR"), revision: 2 }));
  expect(
    summary().getByText("The saved view differs from both compared states."),
  ).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("serializes rapid read clicks without sending a PATCH", async () => {
  const f = await setup();
  await lose(f);
  let release!: (r: SavedView) => void;
  f.get.mockImplementationOnce(
    () =>
      new Promise((r) => {
        release = r;
      }),
  );
  const button = summary().getByRole("button", {
    name: "Check saved view state",
  });
  act(() => {
    fireEvent.click(button);
    fireEvent.click(button);
  });
  expect(f.get).toHaveBeenCalledTimes(2);
  await act(async () =>
    release({ ...f.row, ...definition("EUR"), revision: 2 }),
  );
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("closes and cancels a pending read, retains context, and ignores an obsolete reply after another read", async () => {
  const f = await setup();
  await lose(f);
  let late!: (r: SavedView) => void, oldSignal!: AbortSignal;
  f.get.mockImplementationOnce((_o, _u, _id, s) => {
    oldSignal = s;
    return new Promise((r) => {
      late = r;
    });
  });
  fireEvent.click(
    summary().getByRole("button", { name: "Check saved view state" }),
  );
  fireEvent.click(summary().getByRole("button", { name: "Close summary" }));
  expect(oldSignal.aborted).toBe(true);
  expect(
    panel().getByRole("heading", { name: "My saved views" }),
  ).toHaveFocus();
  fireEvent.click(
    panel().getByRole("button", { name: "Check saved view state" }),
  );
  await screen.findByText("Proposed criteria found in the saved view.");
  await act(async () => late({ ...f.row, revision: 9 }));
  expect(summary().getByText(/Observed version 2/)).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
  expect(f.remove).not.toHaveBeenCalled();
});
it.each(["org", "owner", "membership"])(
  "aborts and clears private attempt state after %s changes",
  async (scope) => {
    const f = await setup();
    await lose(f);
    let late!: (r: SavedView) => void, oldSignal!: AbortSignal;
    f.get.mockImplementationOnce((_o, _u, _id, s) => {
      oldSignal = s;
      return new Promise((r) => {
        late = r;
      });
    });
    fireEvent.click(
      summary().getByRole("button", { name: "Check saved view state" }),
    );
    const props = {
      ...f.props,
      ...(scope === "org"
        ? { org: "bbbbbbbb-0000-4000-8000-000000000001" }
        : scope === "owner"
          ? { owner: "bbbbbbbb-0000-4000-8000-000000000001" }
          : { authorized: false }),
    };
    f.rendered.rerender(<PersonalSavedViews {...props} />);
    expect(oldSignal.aborted).toBe(true);
    await act(async () => late({ ...f.row, revision: 2 }));
    expect(
      screen.queryByRole("region", { name: "Saved view reconciliation" }),
    ).not.toBeInTheDocument();
    expect(
      panel().queryByText(/CFO watchlist|local-1/),
    ).not.toBeInTheDocument();
  },
);
it("selecting a different homonymous view discards the previous context and stale read", async () => {
  const f = await setup();
  await lose(f);
  let release!: (r: SavedView) => void;
  f.get.mockImplementationOnce(
    () =>
      new Promise((r) => {
        release = r;
      }),
  );
  fireEvent.click(
    summary().getByRole("button", { name: "Check saved view state" }),
  );
  // Same visible name is not an identity; use an explicitly different row from a new list read.
  const other = { ...f.row, id: "bbbbbbbb-0000-4000-8000-000000000001" };
  vi.spyOn(f.gateway, "list").mockResolvedValue({
    items: [other],
    limit: 10,
    max_views: 50,
    has_more: false,
    next_after: null,
  });
  fireEvent.change(
    panel().getByRole("textbox", { name: "Find personal views" }),
    { target: { value: "CFO" } },
  );
  await screen.findByRole("button", {
    name: "Manage saved view CFO watchlist",
  });
  f.get.mockResolvedValueOnce(other);
  fireEvent.click(
    panel().getByRole("button", { name: "Manage saved view CFO watchlist" }),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("region", { name: "Saved view reconciliation" }),
    ).not.toBeInTheDocument(),
  );
  await act(async () => release({ ...f.row, revision: 10 }));
  expect(panel().getByText(/Server version 1/)).toBeInTheDocument();
  expect(f.update).toHaveBeenCalledTimes(1);
});
it("a component reload honestly loses attempt attribution and does not persist context or secrets", async () => {
  const f = await setup();
  await lose(f);
  expect(
    summary().getByText(/Local attempt reference local-1/),
  ).toBeInTheDocument();
  f.rendered.unmount();
  render(<PersonalSavedViews {...f.props} />);
  expect(
    panel().getByText(
      /After a page reload, attribution of a prior operation is unavailable/,
    ),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("region", { name: "Saved view reconciliation" }),
  ).not.toBeInTheDocument();
  expect(panel().queryByText(/local-1/)).not.toBeInTheDocument();
});
it("summary contains no financial values, raw IDs, decision evidence or credential/cursor state", async () => {
  const f = await setup();
  await lose(f);
  await check();
  const text = screen.getByRole("region", {
    name: "Saved view reconciliation",
  }).textContent;
  expect(text).not.toMatch(
    new RegExp(
      `${f.row.id}|${org}|${owner}|1,380|9,600|Bearer|after=|citation|Successfully saved`,
    ),
  );
  expect(f.remove).not.toHaveBeenCalled();
});
it.each([
  "lost-applied",
  "lost-previous",
  "lost-different",
  "lost-read-once",
] as const)(
  "keeps the %s demo exercise explicitly synthetic",
  async (exercise) => {
    const gateway = withSyntheticSavedViews(
      createDemoGateway(),
      false,
      exercise,
    ).savedViews!;
    const row = await gateway.create(
      org,
      owner,
      "Demo",
      definition("USD"),
      signal(),
    );
    await expect(
      gateway.update(
        org,
        owner,
        row.id,
        1,
        { definition: definition("EUR") },
        signal(),
      ),
    ).rejects.toThrow(/Synthetic/);
    if (exercise === "lost-read-once")
      await expect(
        gateway.get(org, owner, row.id, signal()),
      ).rejects.toMatchObject({ status: 503 });
    const fresh = await gateway.get(org, owner, row.id, signal());
    expect(fresh.revision).toBe(
      exercise === "lost-previous" ? 1 : exercise === "lost-different" ? 3 : 2,
    );
  },
);
