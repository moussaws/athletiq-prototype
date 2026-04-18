"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { API_BASE, type CohortProvenance } from "../lib/api";

type NavItem = { href: string; label: string; desc: string };

const NAV_GROUPS: { group: string; items: NavItem[] }[] = [
  {
    group: "Start here",
    items: [
      { href: "/", label: "Overview", desc: "Product map + cohort" },
      { href: "/demo", label: "Guided tour", desc: "Three coach stories" },
    ],
  },
  {
    group: "Analyse",
    items: [
      { href: "/matches", label: "Match debrief", desc: "Real open-data games" },
      { href: "/cv", label: "Tape view", desc: "Footage → pitch" },
      { href: "/metrics", label: "Metrics lab", desc: "Pressure · xT · DDI" },
    ],
  },
  {
    group: "Build",
    items: [
      { href: "/recruit", label: "Recruit brief", desc: "Role + style in plain English" },
      { href: "/squad", label: "Squad optimizer", desc: "Pick a philosophy" },
      { href: "/scouting", label: "Scouting", desc: "Archetypes + similar" },
    ],
  },
  {
    group: "Data",
    items: [{ href: "/players", label: "Player directory", desc: "Real Big-5 cohort" }],
  },
];

function useCohort(): CohortProvenance | null {
  const [meta, setMeta] = useState<CohortProvenance | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/players/meta/cohort`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => {
        if (!cancelled && json) setMeta(json as CohortProvenance);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  return meta;
}

function CohortBadge({ meta }: { meta: CohortProvenance | null }) {
  const source = meta?.provenance?.source ?? "";
  const isReal = source.toLowerCase().startsWith("fbref");
  const label = isReal ? "FBRef Big-5 · 2023-24" : "Synthetic cohort";
  const n = meta?.total ?? (isReal ? 816 : 240);
  return (
    <div
      className="chip chip-accent"
      title={meta?.provenance?.proxy_note ?? source}
    >
      <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-accent" />
      <span className="font-mono normal-case tracking-normal text-[0.7rem] text-white">
        {n.toLocaleString()}
      </span>
      <span>{label}</span>
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const meta = useCohort();

  return (
    <div className="relative min-h-screen">
      <div className="pointer-events-none fixed inset-0 bg-grid-lines bg-grid opacity-[0.35] [mask-image:radial-gradient(ellipse_at_top,black_40%,transparent_75%)]" />
      <div className="relative flex min-h-screen">
        <aside className="sticky top-0 z-10 hidden h-screen w-64 shrink-0 flex-col border-r border-white/5 bg-ink-900/60 backdrop-blur-lg lg:flex">
          <div className="flex items-center gap-2 px-6 pt-6">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent via-electric to-magenta text-ink-950 shadow-glow">
              <svg
                viewBox="0 0 24 24"
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <circle cx="12" cy="12" r="9" />
                <path d="M12 3v18M3 12h18" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </div>
            <div className="font-display text-lg font-semibold tracking-tightest">
              AthletIQ
            </div>
          </div>
          <div className="px-6 pb-4 pt-1 text-2xs uppercase tracking-[0.18em] text-white/40">
            Football intelligence
          </div>
          <nav className="flex-1 overflow-y-auto px-4 pb-6">
            {NAV_GROUPS.map((grp) => (
              <div key={grp.group} className="mt-4 first:mt-0">
                <div className="px-2 pb-1 text-2xs font-semibold uppercase tracking-[0.2em] text-white/30">
                  {grp.group}
                </div>
                <div className="flex flex-col">
                  {grp.items.map((item) => {
                    const active =
                      pathname === item.href ||
                      (item.href !== "/" && pathname?.startsWith(item.href));
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`group flex flex-col rounded-lg px-2 py-1.5 transition ${
                          active
                            ? "bg-white/[0.06] text-white"
                            : "text-white/70 hover:bg-white/[0.04] hover:text-white"
                        }`}
                      >
                        <span className="flex items-center gap-2 text-sm font-medium">
                          {active && (
                            <span className="h-1.5 w-1.5 rounded-full bg-accent shadow-glow" />
                          )}
                          {!active && (
                            <span className="h-1.5 w-1.5 rounded-full bg-white/20 group-hover:bg-white/40" />
                          )}
                          {item.label}
                        </span>
                        <span className="ml-3.5 text-2xs text-white/40">
                          {item.desc}
                        </span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
          <div className="border-t border-white/5 p-4 text-2xs text-white/40">
            <div className="flex items-center justify-between">
              <span>FastAPI · Next.js</span>
              <span className="font-mono">v0.1.0</span>
            </div>
          </div>
        </aside>

        <div className="flex-1">
          <header className="sticky top-0 z-20 border-b border-white/5 bg-ink-950/60 backdrop-blur-lg">
            <div className="flex items-center justify-between gap-4 px-6 py-3 lg:px-10">
              <div className="flex items-center gap-3 lg:hidden">
                <div className="font-display text-base font-semibold tracking-tightest">
                  AthletIQ
                </div>
              </div>
              <div className="hidden items-center gap-2 lg:flex">
                <span className="section-title">Live data</span>
                <CohortBadge meta={meta} />
              </div>
              <div className="flex items-center gap-2">
                <Link href="/demo" className="btn-ghost hidden sm:inline-flex">
                  Start tour
                </Link>
                <Link href="/squad" className="btn-primary">
                  Build XI
                </Link>
              </div>
            </div>
          </header>
          <main className="relative px-6 py-10 lg:px-10">
            <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-96 bg-mesh-primary opacity-80" />
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
