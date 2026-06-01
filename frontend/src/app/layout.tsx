import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HSC AI Platform",
  description: "NSW exam preparation — OC and Selective School practice",
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
