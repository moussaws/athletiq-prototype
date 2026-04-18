import Link from "next/link";
import { api, type StatsBombMatchesResponse } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SeasonMatchesPage({
  params,
}: {
  params: { slug: string };
}) {
  const [compStr, seasonStr] = params.slug.split("-");
  const competition_id = parseInt(compStr, 10);
  const season_id = parseInt(seasonStr, 10);
  let data: StatsBombMatchesResponse | null = null;
  let error: string | null = null;

  if (!Number.isFinite(competition_id) || !Number.isFinite(season_id)) {
    error = `invalid slug: ${params.slug} (expected "<competition_id>-<season_id>")`;
  } else {
    try {
      data = await api<StatsBombMatchesResponse>(
        `/api/statsbomb/matches?competition_id=${competition_id}&season_id=${season_id}`,
      );
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  return (
    <div className="max-w-5xl">
      <Link href="/matches" className="text-sm text-accent hover:underline">
        ← back to competitions
      </Link>
      <h1 className="mt-4 text-3xl font-semibold">
        Matches · competition {competition_id} · season {season_id}
      </h1>

      {error && (
        <div className="mt-4 rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {data && (
        <div className="mt-6 overflow-hidden rounded border border-white/10">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-white/60">
              <tr>
                <th className="px-4 py-2">Date</th>
                <th className="px-4 py-2">Home</th>
                <th className="px-4 py-2 text-center">Score</th>
                <th className="px-4 py-2">Away</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((m) => (
                <tr key={m.match_id} className="border-t border-white/5">
                  <td className="px-4 py-2 text-white/70">{m.match_date}</td>
                  <td className="px-4 py-2 font-medium">{m.home_team}</td>
                  <td className="px-4 py-2 text-center tabular-nums">
                    {m.home_score} – {m.away_score}
                  </td>
                  <td className="px-4 py-2 font-medium">{m.away_team}</td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      href={`/matches/match/${m.match_id}`}
                      className="text-accent hover:underline"
                    >
                      open →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-white/5 bg-white/5 px-4 py-2 text-xs text-white/50">
            {data.total} matches
          </div>
        </div>
      )}
    </div>
  );
}
