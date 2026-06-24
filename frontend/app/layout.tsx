import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "kstarid.cloud — Disposable Email",
  description: "Generate temporary email addresses that auto-expire.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
