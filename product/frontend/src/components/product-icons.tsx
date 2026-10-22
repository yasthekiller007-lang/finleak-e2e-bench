import type { CSSProperties } from "react";

export type IconName =
  | "overview"
  | "invoice"
  | "contract"
  | "anomaly"
  | "review"
  | "search"
  | "arrow"
  | "shield"
  | "upload"
  | "check"
  | "clock"
  | "chevron"
  | "external"
  | "refresh";
const paths: Record<IconName, string> = {
  overview: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  invoice: "M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h5",
  contract: "M8 3h12v15H8zM4 7v14h12M11 7h6M11 11h6M11 15h3",
  anomaly: "m12 3 10 18H2zM12 9v5M12 17v.1",
  review: "M9 3h6l1 3h4v15H4V6h4zM9 3v4h6V3M8 13l2 2 5-5M8 18h8",
  search: "M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15ZM16 16l5 5",
  arrow: "M4 12h15m-5-5 5 5-5 5",
  shield: "m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6zM8 12l3 3 5-6",
  upload: "M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6",
  check: "m5 12 4 4L19 6",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l4 2",
  chevron: "m9 5 7 7-7 7",
  external: "M14 3h7v7m0-7L10 14M10 3H3v18h18v-7",
  refresh: "M20 7V3l-4 4M4 17v4l4-4M20 7a8 8 0 0 0-14-2M4 17a8 8 0 0 0 14 2",
};
export function ProductIcon({
  name,
  size = 20,
  style,
}: {
  name: IconName;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      <path d={paths[name]} />
    </svg>
  );
}
