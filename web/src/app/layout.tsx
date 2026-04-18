import "./globals.css";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AthletIQ — Prototype",
  description:
    "Functional prototype for the AthletIQ deeptech football analytics system.",
};

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/players", label: "Players" },
  { href: "/scouting", label: "Scouting" },
  { href: "/squad", label: "Squad" },
  { href: "/metrics", label: "Metrics" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="flex min-h-screen">
          <aside className="w-56 shrink-0 border-r border-white/10 bg-rail p-5 text-sm">
            <div className="mb-8 text-lg font-semibold tracking-tight">
              AthletIQ
              <span className="ml-2 rounded bg-accent/20 px-1.5 py-0.5 text-xs text-accent">
                prototype
              </span>
            </div>
            <nav className="flex flex-col gap-1">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded px-2 py-1.5 text-white/70 hover:bg-white/5 hover:text-white"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="mt-8 text-xs text-white/40">
              <div>backend: FastAPI</div>
              <div>v0.1.0</div>
            </div>
          </aside>
          <main className="flex-1 overflow-x-hidden p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
