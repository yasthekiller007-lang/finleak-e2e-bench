import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/backend";
import { ExceptionViewWorkspace } from "@/components/exception-view-workspace";
import { searchFromRecord } from "@/lib/exception-view-url";
import { ProductConsole } from "@/components/product-console";
import type { ProductView } from "@/lib/product-workspace";

export type ProductSearchParams = Promise<
  Record<string, string | string[] | undefined>
>;

export async function ProductWorkspacePage({
  view,
  searchParams,
}: {
  view: ProductView;
  searchParams?: ProductSearchParams;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  const query = (await searchParams) ?? {};
  if (view === "anomalies" || view === "review") {
    const initialSearch = searchFromRecord(query);
    return (
      <ExceptionViewWorkspace
        key={`${view}:${initialSearch}`}
        user={user}
        view={view}
        initialSearch={initialSearch}
      />
    );
  }
  const org = typeof query.org === "string" ? query.org : "";
  const invoice = typeof query.invoice === "string" ? query.invoice : "";
  const assessment =
    typeof query.assessment === "string" ? query.assessment : "";
  return (
    <ProductConsole
      key={`${view}:${org}:${invoice}:${assessment}`}
      user={user}
      view={view}
      initialOrg={org}
      initialInvoice={invoice}
      initialAssessment={assessment}
    />
  );
}
