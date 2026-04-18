import Link from "next/link";

const CARDS = [
  {
    title: "Guided tour",
    body: "Three coach-level questions AthletIQ answers end-to-end — match debrief, scouting brief, pressing XI. Start here if you're new.",
    href: "/demo",
  },
  {
    title: "Match debrief (real open-data matches)",
    body: "Pick a real match from StatsBomb open data and get a coach-facing narrative: who dominated, who did what, plus raw event totals in Analyst view.",
    href: "/matches",
  },
  {
    title: "Recruit — coach brief",
    body: "Describe the player you want in football language (role + style + caps). We translate it to the criteria and rank the cohort by fit.",
    href: "/recruit",
  },
  {
    title: "Squad optimizer — pick a philosophy",
    body: "Press-heavy / Possession / Direct / Balanced preset → optimal XI on your budget. Raw AHP matrix is one click away in Analyst view.",
    href: "/squad",
  },
  {
    title: "Scouting — archetypes & similar players",
    body: "PCA → silhouette-K-Means archetypes (paper's labels: Deep-Lying Playmaker, Mezzala, etc.) + hybrid KNN retrieval.",
    href: "/scouting",
  },
  {
    title: "Tape view — from footage to pitch",
    body: "Drop a single-camera clip in and see your players projected onto a 105×68 m pitch: shape, compactness, horizontal spread.",
    href: "/cv",
  },
  {
    title: "Context-aware metrics",
    body: "Pressure field, PABR, pressure-weighted carry xT, Pitch Control surface, DDI leaderboard. Equations 1–9.",
    href: "/metrics",
  },
  {
    title: "Player directory",
    body: "240 synthetic players across 8 positions, with realistic position-specific feature archetypes.",
    href: "/players",
  },
];

export default function HomePage() {
  return (
    <div className="max-w-5xl">
      <h1 className="text-3xl font-semibold">AthletIQ prototype</h1>
      <p className="mt-2 max-w-2xl text-white/60">
        Functional prototype of the three-pillar analytics system: context-aware
        metrics, AI scouting, and single-camera CV. Backed by a FastAPI service
        on <code className="text-accent">:8000</code>.
      </p>
      <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        {CARDS.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className="rounded-lg border border-white/10 bg-white/5 p-5 transition hover:border-accent/50 hover:bg-white/10"
          >
            <div className="text-base font-medium">{c.title}</div>
            <p className="mt-2 text-sm text-white/60">{c.body}</p>
            <div className="mt-4 text-xs text-accent">open →</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
