import Link from "next/link";
import {
  api,
  type Player,
  type PlayerStyleResponse,
  type SimilarityResponse,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SimilarPage({
  params,
}: {
  params: { id: string };
}) {
  let data: SimilarityResponse | null = null;
  let query: Player | null = null;
  let style: PlayerStyleResponse | null = null;
  let error: string | null = null;
  try {
    const [similar, player] = await Promise.all([
      api<SimilarityResponse>(`/api/scouting/similar/${params.id}?k=10`),
      api<Player>(`/api/players/${params.id}`),
    ]);
    data = similar;
    query = player;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }
  // Style is a presentation-only add-on; a failure here must NOT wipe out
  // the similar-profiles table or the player header. Fetch it separately so
  // the {style && ...} gate in the JSX can degrade gracefully.
  try {
    style = await api<PlayerStyleResponse>(`/api/scouting/style/${params.id}`);
  } catch {
    style = null;
  }

  if (error) {
    return (
      <div className="max-w-3xl">
        <Link href="/scouting" className="text-sm text-accent hover:underline">
          ← back
        </Link>
        <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      </div>
    );
  }

  const results = data?.results ?? [];

  return (
    <div className="max-w-4xl">
      <Link href="/scouting" className="text-sm text-accent hover:underline">
        ← back to scouting
      </Link>

      {query && (
        <div className="mt-4 rounded border border-white/10 bg-white/5 p-5">
          <div className="text-2xl font-semibold">{query.name}</div>
          <div className="mt-1 text-sm text-white/60">
            {query.position} · {query.nationality} · {query.age}y ·
            {" "}€{query.market_value_m.toFixed(1)}M
          </div>
          {style && (
            <div className="mt-4 border-t border-white/10 pt-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-accent/20 px-2 py-0.5 text-xs font-medium text-accent">
                  {style.archetype_name}
                </span>
                {style.archetype_key_traits.map((t) => (
                  <span
                    key={t}
                    className="rounded border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-white/70"
                  >
                    {t}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-sm text-white/80">{style.style}</p>
              <p className="mt-1 text-xs text-white/50">
                {style.archetype_description}
              </p>
            </div>
          )}
        </div>
      )}

      <h2 className="mt-8 text-lg font-medium">Similar profiles</h2>
      <p className="mt-1 text-sm text-white/50">
        Players with the nearest tactical fingerprint to{" "}
        {query?.name ?? "this player"}. Ranked by a hybrid distance in the
        reduced PCA space — coaches can treat the top rows as credible
        replacements or squad-depth options.
      </p>
      <details className="mt-1 text-xs text-white/40">
        <summary className="cursor-pointer select-none">Analyst view</summary>
        <p className="mt-1">
          λ·Euclidean + (1−λ)·(1−cos), λ={data?.lam.toFixed(2) ?? "0.50"}.
        </p>
      </details>
      <div className="mt-4 overflow-hidden rounded border border-white/10">
        <table className="w-full text-sm">
          <thead className="bg-white/5 text-left text-white/60">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Pos</th>
              <th className="px-4 py-2 text-right">Similarity</th>
              <th className="px-4 py-2 text-right">Euclidean</th>
              <th className="px-4 py-2 text-right">Cosine</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.player_id} className="border-t border-white/5">
                <td className="px-4 py-2">
                  <Link
                    href={`/scouting/${r.player_id}`}
                    className="text-accent hover:underline"
                  >
                    {r.name}
                  </Link>
                </td>
                <td className="px-4 py-2 text-white/70">{r.position}</td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {r.similarity.toFixed(3)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {r.euclidean.toFixed(3)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {r.cosine_similarity.toFixed(3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
