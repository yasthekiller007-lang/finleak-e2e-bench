/** Explicit in-memory synthetic repository. Never used by the authenticated gateway. */
import type { WorkspaceGateway } from "@/lib/product-workspace";
import { demoUser } from "@/lib/product-demo";
import {
  parseSavedView,
  savedDefinition,
  savedName,
  SavedViewsError,
  type SavedView,
} from "@/lib/saved-views";
export type SavedViewExercise =
  | "normal"
  | "lost-applied"
  | "lost-previous"
  | "lost-different"
  | "lost-read-once";
export type RenameExercise =
  | "rename-lost-applied"
  | "rename-lost-previous"
  | "rename-lost-different"
  | "rename-lost-read-once";
export function withSyntheticSavedViews(
  gateway: WorkspaceGateway,
  seed = true,
  exercise: SavedViewExercise | RenameExercise = "normal",
): WorkspaceGateway {
  const org = demoUser.organizations[0].id,
    owner = demoUser.id;
  const rows = new Map<string, SavedView>();
  let sequence = 7000;
  let faultInjected = false,
    failNextRead = false;
  const check = (o: string, u: string, signal: AbortSignal) => {
    signal.throwIfAborted();
    if (o !== org || u !== owner)
      throw new SavedViewsError("Synthetic personal view not found.", 404);
  };
  const read = (id: string) => {
    const row = rows.get(id);
    if (!row)
      throw new SavedViewsError("Synthetic personal view not found.", 404);
    return row;
  };
  const duplicate = (name: string, type: string, except = "") => {
    if (
      [...rows.values()].some(
        (r) =>
          r.id !== except &&
          r.view_type === type &&
          r.name.normalize("NFKC").toLowerCase() ===
            name.normalize("NFKC").toLowerCase(),
      )
    )
      throw new SavedViewsError(
        "Synthetic name conflict. Re-read the view.",
        409,
      );
  };
  if (seed) {
    const id = `00000000-0000-4000-8000-${String(sequence++).padStart(12, "0")}`;
    rows.set(id, {
      id,
      organization_id: org,
      user_id: owner,
      name: "Cloud invoice review",
      view_type: "anomalies",
      format_version: 1,
      criteria: {
        supplier: "AcmeCloud",
        currency: "USD",
        sort: "newest",
        needs_review: false,
      },
      page_size: 2,
      revision: 1,
      created_at: "2026-10-19T00:00:00Z",
      updated_at: "2026-10-19T00:00:00Z",
    });
  }
  return {
    ...gateway,
    savedViews: {
      async list(o, u, view, search, after, signal) {
        check(o, u, signal);
        const values = [...rows.values()]
          .filter(
            (r) =>
              r.view_type === view &&
              r.name.toLowerCase().includes(search.toLowerCase()) &&
              (!after || r.id > after),
          )
          .sort((a, b) => a.id.localeCompare(b.id));
        const items = values.slice(0, 10).map((r) => structuredClone(r));
        return {
          items,
          limit: 10,
          has_more: values.length > 10,
          next_after: values.length > 10 ? items.at(-1)!.id : null,
          max_views: 50,
        };
      },
      async get(o, u, id, signal) {
        check(o, u, signal);
        if (failNextRead) {
          failNextRead = false;
          throw new SavedViewsError(
            "Synthetic reconciliation read unavailable.",
            503,
          );
        }
        return structuredClone(read(id));
      },
      async create(o, u, name, definition, signal) {
        check(o, u, signal);
        name = savedName(name);
        const d = savedDefinition(definition, true);
        duplicate(name, d.view_type);
        if (rows.size >= 50)
          throw new SavedViewsError(
            "Synthetic personal view limit reached.",
            409,
          );
        const id = `00000000-0000-4000-8000-${String(sequence++).padStart(12, "0")}`;
        const now = new Date().toISOString();
        const row = parseSavedView(
          {
            ...d,
            id,
            organization_id: o,
            user_id: u,
            name,
            revision: 1,
            created_at: now,
            updated_at: now,
          },
          o,
          u,
          true,
        );
        rows.set(id, row);
        return structuredClone(row);
      },
      async update(o, u, id, revision, patch, signal) {
        check(o, u, signal);
        const current = read(id);
        if (current.revision !== revision)
          throw new SavedViewsError(
            "Synthetic version conflict. Your draft was retained.",
            409,
          );
        const inject = Boolean(
          (exercise.startsWith("rename-")
            ? patch.name !== undefined
            : patch.definition) &&
          exercise !== "normal" &&
          !faultInjected,
        );
        if (inject) faultInjected = true;
        const scenario = exercise.replace(/^rename-/, "");
        if (inject && scenario === "lost-previous")
          throw new DOMException(
            "Synthetic timeout; write outcome unknown to the UI.",
            "TimeoutError",
          );
        const name =
            patch.name === undefined ? current.name : savedName(patch.name),
          d = patch.definition
            ? savedDefinition(patch.definition, true)
            : {
                view_type: current.view_type,
                format_version: current.format_version,
                criteria: current.criteria,
                page_size: current.page_size,
              };
        if (d.view_type !== current.view_type)
          throw Error("Cannot change a personal view type.");
        duplicate(name, d.view_type, id);
        const row = {
          ...current,
          ...d,
          name,
          revision: revision + 1,
          updated_at: new Date().toISOString(),
        };
        rows.set(id, row);
        if (inject) {
          if (scenario === "lost-different")
            rows.set(id, {
              ...row,
              criteria: { ...row.criteria, q: "Synthetic later-tab criteria" },
              revision: row.revision + 1,
            });
          if (scenario === "lost-read-once") failNextRead = true;
          throw new Error(
            `Synthetic ${exercise.startsWith("rename-") ? "rename" : "replacement"} response lost; outcome unknown to the UI.`,
          );
        }
        return structuredClone(row);
      },
      async remove(o, u, id, revision, signal) {
        check(o, u, signal);
        if (read(id).revision !== revision)
          throw new SavedViewsError("Synthetic version conflict.", 409);
        rows.delete(id);
      },
    },
  };
}
