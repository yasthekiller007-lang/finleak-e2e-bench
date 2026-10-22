import type { Metadata } from "next";
import {
  ProductWorkspacePage,
  type ProductSearchParams,
} from "@/components/product-workspace-page";
export const metadata: Metadata = { title: "Human review" };
export const dynamic = "force-dynamic";
export default function ReviewPage({
  searchParams,
}: {
  searchParams?: ProductSearchParams;
}) {
  return <ProductWorkspacePage view="review" searchParams={searchParams} />;
}
