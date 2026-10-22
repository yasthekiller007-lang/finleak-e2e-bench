"use client";
import { useCallback, useRef, useState, useSyncExternalStore } from "react";
import { ProductConsole } from "@/components/product-console";
import type { CurrentUser } from "@/lib/documents";
import type { WorkspaceGateway } from "@/lib/product-workspace";
import type { ExceptionQuery } from "@/lib/server-exceptions";
import {
  absoluteViewLink,
  MAX_VIEW_URL,
  readViewSearch,
  viewDefaults,
  viewPath,
  type ExceptionView,
  type RestoredView,
} from "@/lib/exception-view-url";

function locationStore(initialSearch: string) {
  let snapshot = { search: initialSearch, revision: 0, ready: false };
  const server = snapshot;
  const listeners = new Set<() => void>();
  const read = () => {
    snapshot = {
      search: window.location.search,
      revision: snapshot.revision + 1,
      ready: true,
    };
    for (const listener of listeners) listener();
  };
  return {
    getSnapshot: () => snapshot,
    getServerSnapshot: () => server,
    subscribe(listener: () => void) {
      listeners.add(listener);
      window.addEventListener("popstate", read);
      if (!snapshot.ready) read();
      return () => {
        listeners.delete(listener);
        window.removeEventListener("popstate", read);
      };
    },
    write(path: string, restore: boolean) {
      // Preserve Next's history metadata. Own acknowledged criteria do not remount the queue.
      window.history.pushState(window.history.state, "", path);
      if (restore) read();
    },
  };
}
function AppliedWorkspace({
  user,
  view,
  demo,
  gateway,
  restored,
  store,
}: {
  user: CurrentUser;
  view: ExceptionView;
  demo: boolean;
  gateway?: WorkspaceGateway;
  restored: RestoredView;
  store: ReturnType<typeof locationStore>;
}) {
  const applied = useRef(
    viewPath(restored.org, restored.filters, restored.limit, view, demo),
  );
  const onApplied = useCallback(
    (filters: ExceptionQuery, limit: number) => {
      const path = viewPath(restored.org, filters, limit, view, demo);
      absoluteViewLink(window.location.origin, path);
      if (path !== applied.current) {
        store.write(path, false);
        applied.current = path;
      }
    },
    [restored.org, view, demo, store],
  );
  const makeLink = useCallback(
    (filters: ExceptionQuery, limit: number) =>
      absoluteViewLink(
        window.location.origin,
        viewPath(restored.org, filters, limit, view, demo),
      ),
    [restored.org, view, demo],
  );
  return (
    <ProductConsole
      user={user}
      view={view}
      gateway={gateway}
      demo={demo}
      initialOrg={restored.org}
      initialAssessment={restored.assessment}
      initialInvoice={restored.filters.invoice_source_id ?? ""}
      initialExceptionFilters={restored.filters}
      initialExceptionLimit={restored.limit}
      onExceptionApplied={onApplied}
      makeViewLink={makeLink}
      onOrganizationChange={(org) => {
        if (user.organizations.some((o) => o.id === org))
          store.write(
            viewPath(org, viewDefaults(view), demo ? 2 : 20, view, demo),
            true,
          );
      }}
    />
  );
}
export function ExceptionViewWorkspace({
  user,
  view,
  demo = false,
  gateway,
  initialSearch = "",
}: {
  user: CurrentUser;
  view: ExceptionView;
  demo?: boolean;
  gateway?: WorkspaceGateway;
  initialSearch?: string;
}) {
  const [store] = useState(() => locationStore(initialSearch));
  const location = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot,
  );
  if (!location.ready)
    return (
      <div className="p-loading" role="status">
        Checking view link and organization access…
      </div>
    );
  let restored: RestoredView;
  try {
    if (window.location.href.length > MAX_VIEW_URL || window.location.hash)
      throw Error();
    restored = readViewSearch(location.search, view, demo);
    restored.org ||= user.organizations[0]?.id ?? "";
    if (!user.organizations.some((o) => o.id === restored.org)) throw Error();
  } catch {
    return (
      <section className="p-card p-view-error" role="alert">
        <h2>View unavailable</h2>
        <p>
          The link is invalid, unsupported or unavailable for your current
          organization access. No financial search was started.
        </p>
        {user.organizations[0] && (
          <button
            onClick={() =>
              store.write(
                viewPath(
                  user.organizations[0].id,
                  viewDefaults(view),
                  demo ? 2 : 20,
                  view,
                  demo,
                ),
                true,
              )
            }
          >
            Open default authorized view
          </button>
        )}
      </section>
    );
  }
  return (
    <AppliedWorkspace
      key={location.revision}
      {...{ user, view, demo, gateway, restored, store }}
    />
  );
}
