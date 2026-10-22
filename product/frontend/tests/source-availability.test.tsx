import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { SourceAvailability } from "@/components/source-availability";
const scan = "11111111-1111-4111-8111-111111111111";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
it("keeps viewers read-only and unknown scan states unavailable", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({ state: "NEW_UNKNOWN_STATE", scan_id: scan }),
    ),
  );
  const availability = vi.fn();
  render(
    <SourceAvailability
      base="/doc"
      role="viewer"
      onAvailability={availability}
    />,
  );
  await screen.findByText("Unavailable: unknown scan outcome");
  expect(availability).toHaveBeenLastCalledWith(false);
  expect(
    screen.queryByRole("button", { name: "Scan exact original" }),
  ).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Release clean original" }),
  ).toBeNull();
});
it("uses the same scan key after a lost response and requires separate release", async () => {
  const calls: RequestInit[] = [];
  let lost = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url, init?: RequestInit) => {
      if (init?.method === "POST") {
        calls.push(init);
        if (lost) {
          lost = false;
          throw new Error("Response lost; refresh before retrying.");
        }
        return Response.json({ source: { state: "CLEAN_AWAITING_RELEASE" } });
      }
      return Response.json({ state: "CLEAN_AWAITING_RELEASE", scan_id: scan });
    }),
  );
  const availability = vi.fn();
  render(
    <SourceAvailability
      base="/doc"
      role="analyst"
      onAvailability={availability}
    />,
  );
  await screen.findByText("Clean scan: awaiting owner/admin release");
  fireEvent.change(screen.getByLabelText("Source action reason"), {
    target: { value: "Synthetic review" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Scan exact original" }));
  await screen.findByRole("alert");
  expect(availability).toHaveBeenLastCalledWith(false);
  fireEvent.click(screen.getByRole("button", { name: "Scan exact original" }));
  await screen.findByText(
    "Scan recorded. Release and financial approval are separate.",
  );
  expect(calls[0].headers).toEqual(calls[1].headers);
  expect(
    screen.queryByRole("button", { name: "Release clean original" }),
  ).toBeNull();
});
it("releases only the exact clean scan with deliberate confirmation", async () => {
  let state = "CLEAN_AWAITING_RELEASE";
  const fetcher = vi.fn(async (_url, init?: RequestInit) => {
    if (init?.method === "POST") state = "RELEASED";
    return Response.json({ state, scan_id: scan });
  });
  vi.stubGlobal("fetch", fetcher);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const availability = vi.fn();
  render(
    <SourceAvailability
      base="/doc"
      role="owner"
      onAvailability={availability}
    />,
  );
  await screen.findByText("Clean scan: awaiting owner/admin release");
  fireEvent.change(screen.getByLabelText("Source action reason"), {
    target: { value: "Synthetic owner review" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Release clean original" }),
  );
  await waitFor(() => expect(availability).toHaveBeenLastCalledWith(true));
  expect(
    JSON.parse(
      fetcher.mock.calls.find((c) => c[1]?.method === "POST")![1]!
        .body as string,
    ),
  ).toEqual({ reason: "Synthetic owner review", scan_id: scan });
  expect(
    await screen.findByText(
      "Original released. No processing or financial workflow has run.",
    ),
  ).toBeInTheDocument();
});
