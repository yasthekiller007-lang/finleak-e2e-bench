import type { Assessment } from "@/lib/financial";
import {
  assessmentLabel,
  documentFor,
  isReviewNeeded,
  type WorkspaceData,
} from "@/lib/product-workspace";

export type QueueFilters = {
  search: string;
  status: string;
  currency: string;
  supplier: string;
  contract: string;
  sort: string;
  invoice: string;
  reviewOnly: boolean;
};
const decimal = (v: string) => /^-?\d{1,100}(?:\.\d{1,30})?$/.test(v);
/** Exact ordering of recorded Decimal strings only; never a financial recalculation. */
export function compareDecimal(a: string, b: string): number {
  if (!decimal(a) || !decimal(b)) throw new Error("Invalid recorded decimal");
  const scale = Math.max(
    a.split(".")[1]?.length ?? 0,
    b.split(".")[1]?.length ?? 0,
  );
  const units = (v: string) => {
    const [whole, fraction = ""] = v.split(".");
    return BigInt(whole + fraction.padEnd(scale, "0"));
  };
  const left = units(a),
    right = units(b);
  return left < right ? -1 : left > right ? 1 : 0;
}
export function contractName(data: WorkspaceData, sourceId: string) {
  const source = data.sources.items.find(
    (s) => s.id === sourceId && s.kind === "contract",
  );
  return (
    data.documents.items.find((d) => d.id === source?.document_id)
      ?.original_filename ?? `Contract source ${sourceId}`
  );
}
export function queueRows(
  data: WorkspaceData,
  filters: QueueFilters,
): Assessment[] {
  const search = filters.search.trim().toLowerCase();
  return data.assessments.items
    .filter((a) => {
      const context = a.queue_context;
      if (filters.reviewOnly && !isReviewNeeded(a)) return false;
      if (filters.invoice && filters.invoice !== a.invoice_source_id)
        return false;
      if (filters.status !== "all" && assessmentLabel(a) !== filters.status)
        return false;
      if (
        filters.currency !== "all" &&
        (a.currency ?? "unknown") !== filters.currency
      )
        return false;
      if (
        filters.supplier !== "all" &&
        JSON.stringify(context?.supplier_party ?? null) !== filters.supplier
      )
        return false;
      if (
        filters.contract !== "all" &&
        JSON.stringify(context?.contract_source_id ?? null) !== filters.contract
      )
        return false;
      return [
        a.scope_summary?.label ?? a.scope_key,
        documentFor(data, a)?.original_filename,
        a.id,
        a.explanation,
        context?.supplier_party,
        ...(context?.contract_references ?? []),
        context?.contract_source_id
          ? contractName(data, context.contract_source_id)
          : "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(search);
    })
    .sort((a, b) => {
      let result = 0;
      if (filters.sort.startsWith("amount_")) {
        // Currencies form separate alphabetical groups. Unknown/nonmonetary rows are last.
        if (!a.currency || !b.currency)
          result = a.currency ? -1 : b.currency ? 1 : 0;
        else result = a.currency.localeCompare(b.currency);
        if (!result && a.currency && b.currency) {
          const validA = a.potential !== null && decimal(a.potential),
            validB = b.potential !== null && decimal(b.potential);
          result =
            validA && validB
              ? compareDecimal(a.potential!, b.potential!) *
                (filters.sort === "amount_high" ? -1 : 1)
              : validA
                ? -1
                : validB
                  ? 1
                  : 0;
        }
      } else if (filters.sort === "status")
        result = assessmentLabel(a).localeCompare(assessmentLabel(b));
      if (!result)
        result =
          filters.sort === "oldest"
            ? a.created_at.localeCompare(b.created_at)
            : b.created_at.localeCompare(a.created_at);
      return result || a.id.localeCompare(b.id);
    });
}
export function mergeRecords<T extends { id: string }>(
  previous: T[],
  next: T[],
): T[] {
  return [
    ...new Map([...previous, ...next].map((row) => [row.id, row])).values(),
  ];
}
export const hasNextWindow = (page: {
  offset: number;
  limit: number;
  total: number;
}) => page.limit > 0 && page.offset + page.limit < page.total;
export function portfolio(data: WorkspaceData) {
  const states = new Map<string, number>();
  const currencies = new Map<
    string,
    { count: number; confirmed: number; waiting: number }
  >();
  for (const currency of Object.keys(data.summary.potential_by_currency))
    currencies.set(currency, { count: 0, confirmed: 0, waiting: 0 });
  for (const a of data.assessments.items) {
    const label = assessmentLabel(a);
    states.set(label, (states.get(label) ?? 0) + 1);
    const currency = a.currency ?? "Unspecified",
      row = currencies.get(currency) ?? { count: 0, confirmed: 0, waiting: 0 };
    row.count++;
    if (!a.stale && a.status === "confirmed") row.confirmed++;
    if (isReviewNeeded(a)) row.waiting++;
    currencies.set(currency, row);
  }
  return {
    states: [...states].sort(([a], [b]) => a.localeCompare(b)),
    currencies: [...currencies].sort(([a], [b]) => a.localeCompare(b)),
  };
}
