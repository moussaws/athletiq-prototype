import Link from "next/link";
import {
  api,
  type StatsBombCapabilities,
  type StatsBombCompetitionsResponse,
} from "@/lib/api";

export const dynamic = "force-dynamic";

function Capability({ caps }: { caps: StatsBombCapabilities }) {
  if (caps.statsbomb_available) {
    return (
      <div className="rounded border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-200">
        StatsBomb open data available — pick a competition to browse matches.
      </div>
    );
  }
  return (
    <div className="rounded border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">
      StatsBomb adapter not installed.
      {caps.reason ? ` ${caps.reason}` : ""}
    </div>
  );
}

export default async function MatchesPage({
  searchParams,
}: {
  searchParams: { gender?: string; q?: string };
}) {
  let caps: StatsBombCapabilities = {
    statsbomb_available: false,
    reason: "backend not reachable",
  };
  let comps: StatsBombCompetitionsResponse | null = null;
  let error: string | null = null;
  try {
    caps = await api<StatsBombCapabilities>("/api/statsbomb/capabilities");
    if (caps.statsbomb_available) {
      comps = await api<StatsBombCompetitionsResponse>(
        "/api/statsbomb/competitions",
      );
    }
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const gender = searchParams.gender ?? "";
  const q = (searchParams.q ?? "").toLowerCase();
  const items = (comps?.items ?? []).filter((c) => {
    if (gender && c.competition_gender !== gender) return false;
    if (q) {
      const hay = `${c.competition_name} ${c.country_name} ${c.season_name}`
        .toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  return (
    <div className="max-w-5xl">
      <h1 className="text-3xl font-semibold">Matches (StatsBomb open data)</h1>
      <p className="mt-2 text-white/60">
        Browse the full open dataset by competition and season. Click a
        competition to see every match; click a match to see both teams&apos;
        players with their AthletIQ feature profile aggregated from raw
        events.
      </p>

      <div className="mt-4">
        <Capability caps={caps} />
      </div>

      {error && (
        <div className="mt-4 rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {comps && (
        <>
          <form className="mt-6 flex flex-wrap gap-2 text-sm" method="get">
            <input
              name="q"
              defaultValue={searchParams.q ?? ""}
              placeholder="Search competition / country / season…"
              className="w-80 rounded border border-white/10 bg-rail px-3 py-1.5 text-white placeholder:text-white/40"
            />
            <select
              name="gender"
              defaultValue={gender}
              className="rounded border border-white/10 bg-rail px-3 py-1.5 text-white"
            >
              <option value="">all genders</option>
              <option value="male">male</option>
              <option value="female">female</option>
            </select>
            <button
              type="submit"
              className="rounded bg-accent/20 px-3 py-1.5 text-accent hover:bg-accent/30"
            >
              filter
            </button>
          </form>

          <div className="mt-6 overflow-hidden rounded border border-white/10">
            <table className="w-full text-sm">
              <thead className="bg-white/5 text-left text-white/60">
                <tr>
                  <th className="px-4 py-2">Competition</th>
                  <th className="px-4 py-2">Country</th>
                  <th className="px-4 py-2">Season</th>
                  <th className="px-4 py-2">Gender</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr
                    key={`${c.competition_id}-${c.season_id}`}
                    className="border-t border-white/5"
                  >
                    <td className="px-4 py-2 font-medium">
                      {c.competition_name}
                    </td>
                    <td className="px-4 py-2 text-white/70">
                      {c.country_name}
                    </td>
                    <td className="px-4 py-2 text-white/70">{c.season_name}</td>
                    <td className="px-4 py-2 text-white/60">
                      {c.competition_gender}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Link
                        href={`/matches/season/${c.competition_id}-${c.season_id}`}
                        className="text-accent hover:underline"
                      >
                        browse matches →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="border-t border-white/5 bg-white/5 px-4 py-2 text-xs text-white/50">
              {items.length} of {comps.total} competitions
            </div>
          </div>
        </>
      )}
    </div>
  );
}
