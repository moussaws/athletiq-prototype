import Link from "next/link";
import { api, type Player, type SimilarityResponse } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SimilarPage({
  params,
}: {
  params: { id: string };
}) {
  let data: SimilarityResponse | null = null;
  let query: Player | null = null;
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
        </div>
      )}

      <h2 className="mt-8 text-lg font-medium">Similar profiles</h2>
      <p className="mt-1 text-sm text-white/50">
        Ranked by hybrid distance λ·Euclidean + (1−λ)·(1−cos), λ=
        {data?.lam.toFixed(2) ?? "0.50"}, in the reduced PCA space.
      </p>
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
