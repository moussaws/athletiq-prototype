import "./globals.css";
import type { Metadata } from "next";

import AppShell from "../components/AppShell";

export const metadata: Metadata = {
  title: "AthletIQ — Football intelligence",
  description:
    "Coach-first football analytics: match debriefs, recruit briefs, squad philosophy optimizer, and single-camera tape projection on 816 real Big-5 2023-24 players.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
