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
      { href: "/lab", label: "Counterfactual Lab", desc: "Drag a defender, re-see Φ" },
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
  const label = isReal
    ? `FBRef Big-5 · ${meta?.provenance?.season ?? "2023-24"}`
    : "Synthetic cohort";
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

function NavGroups({
  pathname,
  onNavigate,
}: {
  pathname: string | null;
  onNavigate?: () => void;
}) {
  return (
    <>
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
                  onClick={onNavigate}
                  className={`group flex flex-col rounded-lg px-2 py-1.5 transition ${
                    active
                      ? "bg-white/[0.06] text-white"
                      : "text-white/70 hover:bg-white/[0.04] hover:text-white"
                  }`}
                >
                  <span className="flex items-center gap-2 text-sm font-medium">
                    {active ? (
                      <span className="h-1.5 w-1.5 rounded-full bg-accent shadow-glow" />
                    ) : (
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
    </>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const meta = useCohort();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

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
            <NavGroups pathname={pathname} />
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
                <button
                  type="button"
                  aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
                  aria-expanded={mobileOpen}
                  onClick={() => setMobileOpen((v) => !v)}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-white/80 transition hover:border-accent/40 hover:text-white"
                >
                  <svg
                    viewBox="0 0 24 24"
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden
                  >
                    {mobileOpen ? (
                      <path d="M6 6l12 12M6 18L18 6" />
                    ) : (
                      <path d="M4 7h16M4 12h16M4 17h16" />
                    )}
                  </svg>
                </button>
                <div className="font-display text-base font-semibold tracking-tightest">
                  AthletIQ
                </div>
                <CohortBadge meta={meta} />
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
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-ink-950/70 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col border-r border-white/10 bg-ink-900/95 shadow-card">
            <div className="flex items-center justify-between px-5 pt-5">
              <div className="font-display text-lg font-semibold tracking-tightest">
                AthletIQ
              </div>
              <button
                type="button"
                aria-label="Close navigation"
                onClick={() => setMobileOpen(false)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-white/80 transition hover:border-accent/40 hover:text-white"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M6 6l12 12M6 18L18 6" />
                </svg>
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto px-3 py-4">
              <NavGroups
                pathname={pathname}
                onNavigate={() => setMobileOpen(false)}
              />
            </nav>
            <div className="border-t border-white/5 p-4 text-2xs text-white/40">
              <div className="flex items-center justify-between">
                <span>FastAPI · Next.js</span>
                <span className="font-mono">v0.1.0</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
