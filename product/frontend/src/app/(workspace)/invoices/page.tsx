import type { Metadata } from "next";
import {
  ProductWorkspacePage,
  type ProductSearchParams,
} from "@/components/product-workspace-page";
export const metadata: Metadata = { title: "Invoices" };
export const dynamic = "force-dynamic";
export default function InvoicesPage({
  searchParams,
}: {
  searchParams?: ProductSearchParams;
}) {
  return <ProductWorkspacePage view="invoices" searchParams={searchParams} />;
}
