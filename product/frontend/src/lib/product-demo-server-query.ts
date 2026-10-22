/** Explicit in-memory server-boundary fixture. Never a PostgreSQL implementation. */
import type { WorkspaceGateway } from "@/lib/product-workspace";
import { WorkspaceError } from "@/lib/product-workspace";
import { compareDecimal } from "@/lib/exception-workbench";
import type { ExceptionRow } from "@/lib/server-exceptions";

export function withSyntheticServerQuery(
  base: WorkspaceGateway,
): WorkspaceGateway {
  let version = 0;
  return {
    ...base,
    async decide(...args) {
      const result = await base.decide(...args);
      version++;
      return result;
    },
    async queryExceptions(org, filters, limit, after, signal) {
      signal.throwIfAborted();
      const data = await base.load(org, signal);
      const binding = JSON.stringify([org, filters, limit]);
      let start = 0;
      if (after) {
        try {
          const cursor = JSON.parse(atob(after));
          if (cursor.binding !== binding || cursor.version !== version)
            throw Error();
          start = cursor.seen;
        } catch {
          throw new WorkspaceError(
            "Synthetic cursor invalidated; restart the query.",
            409,
          );
        }
      }
      let rows: ExceptionRow[] = data.assessments.items.map((row) => {
        const source = data.sources.items.find(
            (s) => s.id === row.invoice_source_id,
          ),
          doc = data.documents.items.find((d) => d.id === source?.document_id);
        const contract = data.sources.items.find(
          (s) => s.id === row.queue_context?.contract_source_id,
        );
        return {
          ...row,
          outcome: row.potential !== null ? "POTENTIAL_LEAKAGE" : row.outcome,
          invoice_document_id: doc?.id,
          invoice_filename: doc?.original_filename,
          contract_filename: data.documents.items.find(
            (d) => d.id === contract?.document_id,
          )?.original_filename,
        };
      });
      const f = filters;
      rows = rows.filter((row) => {
        if (
          f.invoice_source_id &&
          row.invoice_source_id !== f.invoice_source_id
        )
          return false;
        if (f.outcome && row.outcome !== f.outcome) return false;
        if (f.currency && row.currency !== f.currency) return false;
        if (f.supplier && row.queue_context?.supplier_party !== f.supplier)
          return false;
        if (
          f.contract_source_id &&
          row.queue_context?.contract_source_id !== f.contract_source_id
        )
          return false;
        if (f.missing_contract && row.queue_context?.contract_source_id)
          return false;
        if (f.created_from && row.created_at < f.created_from) return false;
        if (f.created_to && row.created_at >= f.created_to) return false;
        if (f.current && row.stale) return false;
        if (
          f.needs_review &&
          (row.stale ||
            !(
              row.outcome === "NEEDS_REVIEW" ||
              (row.potential !== null &&
                row.status !== "confirmed" &&
                row.status !== "false_positive")
            ))
        )
          return false;
        if (
          f.decision_status &&
          (f.decision_status === "unrecorded"
            ? row.decision_id !== null
            : row.status !== f.decision_status)
        )
          return false;
        return (
          !f.q ||
          [
            row.scope_key,
            row.scope_summary?.label,
            row.id,
            row.explanation,
            row.queue_context?.supplier_party,
            ...(row.queue_context?.contract_references ?? []),
          ]
            .join(" ")
            .toLowerCase()
            .includes(f.q.trim().toLowerCase())
        );
      });
      const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
      rows.sort((a, b) => {
        let result = 0;
        if (f.sort?.startsWith("amount_")) {
          result =
            a.currency === null
              ? b.currency === null
                ? 0
                : 1
              : b.currency === null
                ? -1
                : cmp(a.currency, b.currency);
          if (!result && a.currency && b.currency)
            result =
              a.potential === null
                ? b.potential === null
                  ? 0
                  : 1
                : b.potential === null
                  ? -1
                  : compareDecimal(a.potential, b.potential) *
                    (f.sort === "amount_high" ? -1 : 1);
        } else if (f.sort === "outcome") result = cmp(a.outcome, b.outcome);
        else
          result =
            cmp(a.created_at, b.created_at) * (f.sort === "oldest" ? 1 : -1);
        return result || cmp(a.id, b.id);
      });
      const items = rows.slice(start, start + limit),
        more = start + items.length < rows.length;
      return {
        items,
        total: rows.length,
        total_exact: true,
        limit,
        offset: start,
        has_more: more,
        next_cursor: more
          ? btoa(
              JSON.stringify({ binding, version, seen: start + items.length }),
            )
          : null,
        pagination: "cursor",
        consistency:
          "Synthetic fixture only. Financial changes invalidate its demo cursor.",
        coverage:
          "No live backend, PostgreSQL, authentication or SQL pagination is exercised by this demo.",
      };
    },
  };
}
