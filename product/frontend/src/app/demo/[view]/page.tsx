import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { searchFromRecord } from "@/lib/exception-view-url";
import { ProductDemoWorkspace } from "@/components/product-demo-workspace";
import { viewLabels, type ProductView } from "@/lib/product-workspace";
export const metadata: Metadata = {
  title: "Synthetic product demo",
  robots: { index: false, follow: false },
};
export default async function DemoPage({
  params,
  searchParams,
}: {
  params: Promise<{ view: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { view } = await params;
  if (!Object.hasOwn(viewLabels, view)) notFound();
  const query = (await searchParams) ?? {};
  const invoice = typeof query.invoice === "string" ? query.invoice : "";
  const assessment =
    typeof query.assessment === "string" ? query.assessment : "";
  return (
    <ProductDemoWorkspace
      key={`${view}:${searchFromRecord(query)}`}
      view={view as ProductView}
      initialSearch={searchFromRecord(query)}
      initialInvoice={invoice}
      initialAssessment={assessment}
    />
  );
}
