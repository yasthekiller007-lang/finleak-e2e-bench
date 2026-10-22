import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import "./product.css";

export const metadata: Metadata = {
  title: {
    default: "FINLEAK",
    template: "%s · FINLEAK",
  },
  description:
    "Evidence-led financial intelligence for contract and invoice review.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
