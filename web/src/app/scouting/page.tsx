import Link from "next/link";
import {
  api,
  type ArchetypeResponse,
  type PlayersListResponse,
} from "@/lib/api";

export const dynamic = "force-dynamic";

const POSITIONS = ["GK", "CB", "FB", "DM", "CM", "AM", "WG", "ST"] as const;

export default async function ScoutingPage({
  searchParams,
}: {
  searchParams: { position?: string };
}) {
  const position = searchParams.position ?? "CM";

  let data: PlayersListResponse | null = null;
  let error: string | null = null;
  try {
    data = await api<PlayersListResponse>("/api/players?limit=12");
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  let archetypes: ArchetypeResponse | null = null;
  let archError: string | null = null;
  try {
    archetypes = await api<ArchetypeResponse>(
      `/api/scouting/archetypes/${position}`,
    );
  } catch (e) {
    archError = e instanceof Error ? e.message : String(e);
  }

  return (
    <div className="max-w-5xl">
      <h1 className="font-display text-4xl font-semibold tracking-tightest text-white">AI scouting</h1>
      <p className="mt-2 text-white/70">
        Find a replacement, a depth option, or a complementary profile. Every
        player is auto-labelled with a tactical archetype (Regista, Box-to-Box
        Raider, Target Man, …) drawn from how they actually play.
      </p>
      <details className="mt-2 text-xs text-white/40">
        <summary className="cursor-pointer select-none">Analyst view</summary>
        <p className="mt-1">
          Per-position PCA → silhouette-optimal K-Means → hybrid
          Euclidean+cosine KNN retrieval (Eq. 10–11).
        </p>
      </details>

      <section className="mt-8 rounded border border-white/10 bg-white/5 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Tactical archetypes</h2>
          <form method="get" className="text-xs">
            <label className="mr-2 text-white/60">Position</label>
            <select
              name="position"
              defaultValue={position}
              className="rounded border border-white/10 bg-rail px-2 py-1 text-white"
            >
              {POSITIONS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <button
              type="submit"
              className="ml-2 rounded bg-accent/20 px-2 py-1 text-accent hover:bg-accent/30"
            >
              switch
            </button>
          </form>
        </div>
        <p className="mt-1 text-xs text-white/50">
          Coach-facing clusters for <b>{position}</b> — what subtypes actually
          exist in your cohort, with a one-line description and the traits that
          define them.
        </p>

        {archError && (
          <div className="mt-4 rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
            {archError}
          </div>
        )}

        {archetypes && (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
            {archetypes.buckets.map((b) => (
              <div
                key={b.cluster_id}
                className="rounded border border-white/10 bg-rail/60 p-3"
              >
                <div className="flex items-baseline justify-between">
                  <div className="text-sm font-semibold text-accent">
                    {b.name}
                  </div>
                  <div className="text-xs text-white/40">
                    {b.size} player{b.size === 1 ? "" : "s"}
                  </div>
                </div>
                <p className="mt-1 text-xs text-white/70">{b.description}</p>
                {b.key_traits.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {b.key_traits.map((t) => (
                      <span
                        key={t}
                        className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-white/70"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}
                {b.members.length > 0 && (
                  <div className="mt-2 text-[10px] text-white/40">
                    e.g. {b.members.slice(0, 3).join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium">Pick a player</h2>
        <p className="mt-1 text-xs text-white/50">
          Click any player to see their archetype, style summary, and nearest
          replacements.
        </p>

        {error && (
          <div className="mt-4 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
            Backend not reachable: {error}
          </div>
        )}

        {data && (
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
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
      </section>
    </div>
  );
}
