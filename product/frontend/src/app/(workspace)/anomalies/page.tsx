import type { Metadata } from "next";
import {
  ProductWorkspacePage,
  type ProductSearchParams,
} from "@/components/product-workspace-page";
export const metadata: Metadata = { title: "Anomalies" };
export const dynamic = "force-dynamic";
export default function AnomaliesPage({
  searchParams,
}: {
  searchParams?: ProductSearchParams;
}) {
  return <ProductWorkspacePage view="anomalies" searchParams={searchParams} />;
}
