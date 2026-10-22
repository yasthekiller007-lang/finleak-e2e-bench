import type { Metadata } from "next";
import {
  ProductWorkspacePage,
  type ProductSearchParams,
} from "@/components/product-workspace-page";
export const metadata: Metadata = { title: "Overview" };
export const dynamic = "force-dynamic";
export default function DashboardPage({
  searchParams,
}: {
  searchParams?: ProductSearchParams;
}) {
  return <ProductWorkspacePage view="dashboard" searchParams={searchParams} />;
}
