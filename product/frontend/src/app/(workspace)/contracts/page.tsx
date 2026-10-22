import type { Metadata } from "next";
import {
  ProductWorkspacePage,
  type ProductSearchParams,
} from "@/components/product-workspace-page";
export const metadata: Metadata = { title: "Contracts" };
export const dynamic = "force-dynamic";
export default function ContractsPage({
  searchParams,
}: {
  searchParams?: ProductSearchParams;
}) {
  return <ProductWorkspacePage view="contracts" searchParams={searchParams} />;
}
