import Link from "next/link";
import { api, type PlayersListResponse } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ScoutingPage() {
  let data: PlayersListResponse | null = null;
  let error: string | null = null;
  try {
    data = await api<PlayersListResponse>("/api/players?limit=12");
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <div className="max-w-5xl">
      <h1 className="text-3xl font-semibold">AI scouting</h1>
      <p className="mt-2 text-white/60">
        Per-position PCA → silhouette-optimal K-Means → hybrid Euclidean+cosine
        KNN retrieval (Eq. 10–11). Pick a player to find similar profiles in the
        cohort.
      </p>

      {error && (
        <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          Backend not reachable: {error}
        </div>
      )}

      {data && (
        <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3">
          {data.items.map((p) => (
            <Link
              key={p.player_id}
              href={`/scouting/${p.player_id}`}
              className="rounded border border-white/10 bg-white/5 p-4 transition hover:border-accent/50"
            >
              <div className="text-sm font-medium">{p.name}</div>
              <div className="mt-1 text-xs text-white/50">
                {p.position} · {p.nationality} · {p.age}y
              </div>
              <div className="mt-2 text-xs text-accent">
                €{p.market_value_m.toFixed(1)}M
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
