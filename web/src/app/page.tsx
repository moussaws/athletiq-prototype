import Link from "next/link";

import { API_BASE, type CohortProvenance } from "../lib/api";

async function fetchCohort(): Promise<CohortProvenance | null> {
  try {
    const r = await fetch(`${API_BASE}/api/players/meta/cohort`, {
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as CohortProvenance;
  } catch {
    return null;
  }
}

type Card = {
  title: string;
  body: string;
  href: string;
  cta: string;
  accent: "accent" | "electric" | "magenta";
  tag: string;
};

const CARDS: Card[] = [
  {
    title: "Match debrief",
    body: "Pick a real StatsBomb open-data match and get a coach headline with role-tagged top performers. Raw event totals live behind Analyst view.",
    href: "/matches",
    cta: "Open match browser",
    accent: "accent",
    tag: "Analyse",
  },
  {
    title: "Recruit brief",
    body: "Describe the player you want in football language — role, style, budget, age. WASPAS ranks the fit across the live Big-5 cohort.",
    href: "/recruit",
    cta: "Write a brief",
    accent: "electric",
    tag: "Build",
  },
  {
    title: "Squad optimizer",
    body: "Four philosophy presets — Press-heavy · Possession · Direct · Balanced — solve the XI on your budget with foreign caps. Saaty matrix is one click away.",
    href: "/squad",
    cta: "Pick a philosophy",
    accent: "accent",
    tag: "Build",
  },
  {
    title: "Tape view",
    body: "Drop a single-camera clip. YOLOv10 + ByteTrack + per-frame homography project players onto the 105×68 m pitch with a plain-English shape readout.",
    href: "/cv",
    cta: "Upload footage",
    accent: "magenta",
    tag: "Analyse",
  },
  {
    title: "Scouting archetypes",
    body: "PCA → silhouette-tuned K-Means with the paper's archetype labels (Deep-Lying Playmaker, Mezzala, …) and hybrid-distance similar-player retrieval.",
    href: "/scouting",
    cta: "Browse archetypes",
    accent: "electric",
    tag: "Build",
  },
  {
    title: "Metrics lab",
    body: "Context-aware metrics — pressure, PABR, pressure-weighted carry xT, Pitch Control Φ, DDI leaderboard, VAEP-lite action value.",
    href: "/metrics",
    cta: "Explore metrics",
    accent: "accent",
    tag: "Analyse",
  },
  {
    title: "Counterfactual Lab",
    body: "Drag a defender, shift the back line, swap formations — pitch-control Φ recomputes on every edit. First interactive coach-facing counterfactual surface; builds on Umemoto & Fujii (2023) and Spearman (2018).",
    href: "/lab",
    cta: "Open the lab",
    accent: "magenta",
    tag: "Analyse",
  },
];

const PILLARS = [
  { title: "Context-aware metrics", body: "Pressure field, PABR, carry xT, Pitch Control Φ, DDI, VAEP-lite." },
  { title: "AI scouting", body: "PCA + silhouette K-Means + hybrid KNN + AHP + WASPAS + BIP." },
  { title: "Single-camera CV", body: "YOLOv10 + ByteTrack + dynamic Huber-robust homography." },
];

function accentClasses(kind: Card["accent"]): string {
  switch (kind) {
    case "electric":
      return "from-electric/30 via-electric/0 to-transparent";
    case "magenta":
      return "from-magenta/30 via-magenta/0 to-transparent";
    default:
      return "from-accent/30 via-accent/0 to-transparent";
  }
}

export default async function HomePage() {
  const meta = await fetchCohort();
  const source = meta?.provenance?.source ?? "";
  const isReal = source.toLowerCase().startsWith("fbref");
  const total = meta?.total ?? (isReal ? 816 : 240);
  const season = meta?.provenance?.season ?? "2023-24";
  const competitions = meta?.provenance?.competitions ?? [
    "Bundesliga",
    "La Liga",
    "Ligue 1",
    "Premier League",
    "Serie A",
  ];
  const realValues = meta?.provenance?.market_value_real ?? 0;
  const imputedValues = meta?.provenance?.market_value_imputed ?? 0;
  const positions = meta?.positions ?? {};
  const posEntries = Object.entries(positions);

  return (
    <div className="mx-auto max-w-6xl space-y-12">
      <section className="relative overflow-hidden">
        <div className="relative grid grid-cols-1 gap-8 lg:grid-cols-[1.4fr_1fr]">
          <div>
            <div className="flex items-center gap-2">
              <span className="chip chip-accent">
                <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-accent" />
                Live · {isReal ? "real Big-5 cohort" : "synthetic cohort"}
              </span>
              <span className="chip">Season {season}</span>
            </div>
            <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.02] tracking-tightest text-balance text-white sm:text-6xl">
              Football intelligence that{" "}
              <span className="bg-gradient-to-br from-accent via-electric to-magenta bg-clip-text text-transparent">
                thinks like a coach.
              </span>
            </h1>
            <p className="mt-5 max-w-2xl text-pretty text-base text-white/60 sm:text-lg">
              Match debriefs, recruit briefs, squad philosophies, and single-camera
              tape projection — all grounded in {total.toLocaleString()}{" "}
              {isReal ? "real players from Europe\u2019s top five leagues" : "players"}.
              Mathy analyst view is one toggle away.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/demo" className="btn-primary">
                Start the guided tour
                <svg
                  viewBox="0 0 24 24"
                  className="h-3.5 w-3.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M5 12h14M13 5l7 7-7 7" />
                </svg>
              </Link>
              <Link href="/matches" className="btn-ghost">
                Pick a live match
              </Link>
            </div>
          </div>
          <div className="relative">
            <div className="surface relative overflow-hidden p-6">
              <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-accent/20 blur-3xl" />
              <div className="pointer-events-none absolute -bottom-24 -left-10 h-48 w-48 rounded-full bg-electric/15 blur-3xl" />
              <div className="flex items-center justify-between">
                <div className="section-title">Active cohort</div>
                <span className="chip chip-electric">CC0 source</span>
              </div>
              <div className="mt-4 flex items-baseline gap-3">
                <div className="font-display text-5xl font-semibold tracking-tightest text-white">
                  {total.toLocaleString()}
                </div>
                <div className="text-sm text-white/50">players · ≥900 mins</div>
              </div>
              <div className="mt-2 text-sm text-white/60">
                {isReal
                  ? `FBRef Big-5 ${season} via football-data-warehouse.`
                  : "Synthetic generator (fallback mode)."}
              </div>
              <div className="mt-5 flex flex-wrap gap-1.5">
                {competitions.map((c) => (
                  <span key={c} className="chip">
                    {c}
                  </span>
                ))}
              </div>
              {posEntries.length > 0 && (
                <div className="mt-5">
                  <div className="section-title mb-2">By role</div>
                  <div className="grid grid-cols-4 gap-1.5">
                    {posEntries.map(([pos, n]) => (
                      <div
                        key={pos}
                        className="rounded-lg border border-white/10 bg-white/[0.02] px-2 py-1.5 text-center"
                      >
                        <div className="font-mono text-sm font-semibold text-white">
                          {n}
                        </div>
                        <div className="text-2xs uppercase tracking-[0.16em] text-white/40">
                          {pos}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {isReal && realValues + imputedValues > 0 && (
                <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.02] p-3 text-2xs text-white/50">
                  Market value: <span className="text-white/80">{realValues}</span>{" "}
                  real (Transfermarkt) ·{" "}
                  <span className="text-white/80">{imputedValues}</span> imputed
                  (age + output heuristic)
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between">
          <h2 className="section-title">Pillars</h2>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          {PILLARS.map((p, i) => (
            <div key={p.title} className="surface p-5">
              <div className="flex items-center gap-2">
                <span className="font-mono text-2xs text-white/40">
                  0{i + 1}
                </span>
                <div className="font-display text-base font-semibold text-white">
                  {p.title}
                </div>
              </div>
              <p className="mt-2 text-sm text-white/60">{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-end justify-between">
          <div>
            <h2 className="section-title">Jump in</h2>
            <div className="mt-1 font-display text-2xl font-semibold tracking-tightest text-white">
              Pick a workflow
            </div>
          </div>
          <Link href="/demo" className="text-sm text-accent hover:underline">
            Or take the guided tour →
          </Link>
        </div>
        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {CARDS.map((c) => (
            <Link
              key={c.href}
              href={c.href}
              className="group surface surface-hover relative overflow-hidden p-5"
            >
              <div
                className={`pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b ${accentClasses(
                  c.accent,
                )} opacity-40 transition group-hover:opacity-70`}
              />
              <div className="relative flex items-center justify-between">
                <span className="chip">{c.tag}</span>
                <span className="text-2xs uppercase tracking-[0.16em] text-white/30 transition group-hover:text-accent">
                  open →
                </span>
              </div>
              <div className="relative mt-3 font-display text-xl font-semibold tracking-tightest text-white">
                {c.title}
              </div>
              <p className="relative mt-2 text-sm text-white/60">{c.body}</p>
              <div className="relative mt-4 text-xs font-medium text-accent">
                {c.cta} →
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
