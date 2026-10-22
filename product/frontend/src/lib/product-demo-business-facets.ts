/** Explicit small in-memory fixture, not SQL, authentication or an HMAC cursor implementation. */
import {
  facetContext,
  facetOwnFilter,
  type FacetOption,
} from "@/lib/business-facets";
import { WorkspaceError, type WorkspaceGateway } from "@/lib/product-workspace";
export function withSyntheticBusinessFacets(
  base: WorkspaceGateway,
): WorkspaceGateway {
  return {
    ...base,
    async sourceLabel(org, id, kind, signal) {
      const data = await base.load(org, signal);
      const source = data.sources.items.find(
        (s) => s.id === id && s.kind === kind,
      );
      const doc = data.documents.items.find(
        (d) => d.id === source?.document_id,
      );
      if (!source || !doc)
        throw new WorkspaceError("Synthetic selected source unavailable.", 404);
      return {
        value: id,
        label: doc.original_filename,
        document_id: doc.id,
        description: "Synthetic current document label only.",
      };
    },
    async queryFacets(org, filters, facet, search, limit, after, signal) {
      signal.throwIfAborted();
      const effective = facetContext(filters, facet);
      const records = await base.queryExceptions!(
        org,
        effective,
        100,
        null,
        signal,
      );
      if (records.has_more)
        throw new WorkspaceError(
          "Synthetic facet fixture exceeds its explicit 100-row limit.",
          422,
        );
      const version = JSON.stringify(
        records.items.map((r) => [r.id, r.decision_id, r.stale]),
      );
      const binding = JSON.stringify([org, effective, facet, search, limit]);
      let start = 0;
      if (after) {
        try {
          const cursor = JSON.parse(atob(after));
          if (cursor.binding !== binding || cursor.version !== version)
            throw Error();
          start = cursor.seen;
        } catch {
          throw new WorkspaceError(
            "Synthetic facet cursor invalidated; restart the choices.",
            409,
          );
        }
      }
      const options = new Map<string, FacetOption>();
      const compare = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
      for (const row of [...records.items].sort(
        (a, b) => compare(b.created_at, a.created_at) || compare(a.id, b.id),
      )) {
        if (facet === "supplier") {
          const value = row.queue_context?.supplier_party;
          if (value)
            options.set(value, {
              value,
              label: value,
              identity: "snapshot_string",
            });
        } else if (facet === "invoice") {
          const value = row.invoice_source_id;
          if (
            (!effective.invoice_document_id ||
              row.invoice_document_id === effective.invoice_document_id) &&
            !options.has(value)
          ) {
            const filename =
              row.invoice_filename ?? "Synthetic invoice document";
            options.set(value, {
              value,
              label: filename,
              filename,
              document_id: row.invoice_document_id ?? undefined,
              reference: null,
              invoice_reference: null,
              reference_basis: "not_available_in_reviewed_schema",
              supplier_party: row.queue_context?.supplier_party ?? null,
              description: `Recorded supplier: ${row.queue_context?.supplier_party ?? "not returned"} · synthetic reviewed source`,
              context_basis: "synthetic_fixture_only",
            });
          }
        } else {
          const value = row.queue_context?.contract_source_id;
          if (value && !options.has(value)) {
            const filename =
              row.contract_filename ?? "Synthetic contract document";
            const reference = row.queue_context?.contract_references[0] ?? null;
            options.set(value, {
              value,
              label: reference || filename,
              filename,
              reference,
              description: `${filename} · synthetic approved association fixture`,
            });
          }
        }
      }
      const matches = [...options.values()]
        .sort((a, b) => compare(a.value, b.value))
        .filter((o) =>
          [o.label, o.filename]
            .filter(Boolean)
            .join(" ")
            .toLowerCase()
            .includes(search.trim().toLowerCase()),
        );
      const items = matches.slice(start, start + limit),
        more = start + items.length < matches.length;
      return {
        facet,
        items,
        limit,
        has_more: more,
        next_cursor: more
          ? btoa(
              JSON.stringify({ binding, version, seen: start + items.length }),
            )
          : null,
        order: "synthetic_fixture_order",
        ignored_filter: facetOwnFilter[facet],
        coverage:
          "Synthetic in-memory facets only. No live API, PostgreSQL or legal party resolution.",
        consistency: "Demo cursor only; not the authenticated server cursor.",
      };
    },
  };
}
