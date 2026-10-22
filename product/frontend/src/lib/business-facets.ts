import type { ExceptionQuery } from "@/lib/server-exceptions";
export type FacetKind = "supplier" | "contract" | "invoice";
export const facetOwnFilter = {
  supplier: "supplier",
  contract: "contract_source_id",
  invoice: "invoice_source_id",
} as const;
export type FacetOption = {
  value: string;
  label: string;
  description?: string;
  identity?: "snapshot_string";
  reference?: string | null;
  filename?: string;
  document_id?: string;
  invoice_reference?: string | null;
  reference_basis?: string;
  date?: string;
  date_type?: "reviewed_invoice_date" | "reviewed_source_created_at";
  supplier_party?: string | null;
  context_evaluation_id?: string;
  context_basis?: string;
  source_created_at?: string;
  effective_from?: string | null;
  effective_to?: string | null;
};
export type FacetPage = {
  facet: FacetKind;
  items: FacetOption[];
  limit: number;
  has_more: boolean;
  next_cursor: string | null;
  order: string;
  ignored_filter: string;
  coverage: string;
  consistency: string;
};
export function facetContext(
  filters: ExceptionQuery,
  facet: FacetKind,
): ExceptionQuery {
  const effective = { ...filters, sort: "newest" };
  delete effective[facetOwnFilter[facet]];
  return effective;
}
export function facetsPath(
  filters: ExceptionQuery,
  facet: FacetKind,
  search: string,
  limit: number,
  after: string | null,
) {
  const params = new URLSearchParams({ facet, search, limit: String(limit) });
  for (const [name, value] of Object.entries(facetContext(filters, facet)))
    if (value !== undefined && value !== "" && value !== false)
      params.set(name, String(value));
  if (after) params.set("after", after);
  return `financial/exception-facets?${params}`;
}
