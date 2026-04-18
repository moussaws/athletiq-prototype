import Link from "next/link";

const CARDS = [
  {
    title: "Pillar A — Context-aware metrics",
    body: "Pressure field, PABR, pressure-weighted carry xT, Pitch Control surface, DDI. Equations 1–8.",
    href: "/metrics",
  },
  {
    title: "Pillar B — AI scouting",
    body: "PCA → silhouette-K-Means archetypes, hybrid KNN retrieval, AHP + WASPAS + BIP roster optimization.",
    href: "/scouting",
  },
  {
    title: "Squad optimizer",
    body: "Build a pairwise AHP matrix, combine with WASPAS fitness, and solve the BIP for the optimal XI.",
    href: "/squad",
  },
  {
    title: "Player directory",
    body: "240 synthetic players across 8 positions, with realistic position-specific feature archetypes.",
    href: "/players",
  },
  {
    title: "Pillar C — CV pipeline",
    body: "Upload a broadcast MP4 to run YOLOv10 + ByteTrack, then Huber-refined homography to pitch coordinates.",
    href: "/cv",
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
