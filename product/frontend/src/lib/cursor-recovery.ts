import { WorkspaceError } from "@/lib/product-workspace";
export function cursorNeedsRestart(cause: unknown, facet = false) {
  return (
    cause instanceof WorkspaceError &&
    ((cause.status === 409 &&
      cause.code === (facet ? "FACETS_CHANGED" : "EXCEPTIONS_CHANGED")) ||
      (cause.status === 422 &&
        (cause.code === "INVALID_EXCEPTIONS_CURSOR" ||
          (facet && cause.code === "INVALID_FACET_CURSOR"))))
  );
}
