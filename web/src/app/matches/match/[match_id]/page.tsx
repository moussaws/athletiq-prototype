import Link from "next/link";
import {
  api,
  type StatsBombMatchCohortResponse,
  type StatsBombMatchPlayer,
} from "@/lib/api";

export const dynamic = "force-dynamic";

const POS_ORDER = ["GK", "CB", "FB", "DM", "CM", "AM", "WG", "ST"];

function sortPlayers(players: StatsBombMatchPlayer[]): StatsBombMatchPlayer[] {
  return [...players].sort((a, b) => {
    const pa = POS_ORDER.indexOf(a.position);
    const pb = POS_ORDER.indexOf(b.position);
    if (pa !== pb) return pa - pb;
    return b.passes_completed - a.passes_completed;
  });
}

function TeamTable({
  team,
  players,
}: {
  team: string;
  players: StatsBombMatchPlayer[];
}) {
  const rows = sortPlayers(players);
  return (
    <div className="flex-1 overflow-hidden rounded border border-white/10">
      <div className="border-b border-white/10 bg-white/5 px-4 py-2 text-sm font-medium">
        {team} <span className="text-white/50">· {rows.length} players</span>
      </div>
      <table className="w-full text-xs">
        <thead className="bg-white/5 text-left text-white/60">
          <tr>
            <th className="px-3 py-2">Player</th>
            <th className="px-3 py-2">Pos</th>
            <th className="px-3 py-2 text-right">Passes</th>
            <th className="px-3 py-2 text-right">Take-ons</th>
            <th className="px-3 py-2 text-right">Shots</th>
            <th className="px-3 py-2 text-right">Tackles</th>
            <th className="px-3 py-2 text-right">Intcpts</th>
            <th className="px-3 py-2 text-right">xT carry</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.player_id} className="border-t border-white/5">
              <td className="px-3 py-1.5">{p.name}</td>
              <td className="px-3 py-1.5 text-white/70">{p.position}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">
                {p.passes_completed.toFixed(0)}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums">
                {p.take_ons.toFixed(0)}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums">
                {p.shots.toFixed(0)}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums">
                {p.tackles.toFixed(0)}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums">
                {p.interceptions.toFixed(0)}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums text-accent">
                {p.xt_carry.toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function MatchPage({
  params,
}: {
  params: { match_id: string };
}) {
  let data: StatsBombMatchCohortResponse | null = null;
  let error: string | null = null;
  try {
    data = await api<StatsBombMatchCohortResponse>(
      `/api/statsbomb/match/${params.match_id}`,
    );
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const home: StatsBombMatchPlayer[] = [];
  const away: StatsBombMatchPlayer[] = [];
  if (data) {
    for (const p of data.players) {
      if (p.team === data.home_team) home.push(p);
      else if (p.team === data.away_team) away.push(p);
      else home.push(p);
    }
  }

  return (
    <div className="max-w-6xl">
      <Link href="/matches" className="text-sm text-accent hover:underline">
        ← back to competitions
      </Link>

      <h1 className="mt-4 text-3xl font-semibold">Match {params.match_id}</h1>
      {data && (
        <p className="mt-1 text-white/70">
          {data.home_team || "Home"}
          <span className="px-2 text-accent">
            {data.score || "—"}
          </span>
          {data.away_team || "Away"}
        </p>
      )}

      {error && (
        <div className="mt-4 rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {data && (
        <>
          <div className="mt-6 rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/90">
            <span className="font-medium">Data coverage.</span>{" "}
            StatsBomb open data provides event streams but not
            high-frequency tracking, so the AthletIQ indices that need
            tracking (<code>{data.imputed_features.join(", ")}</code>) are
            imputed to position means downstream. Event-derived features
            (passes, take-ons, shots, tackles, interceptions, xT carry)
            are observed directly from this match.
          </div>

          <div className="mt-6 flex flex-col gap-6 lg:flex-row">
            <TeamTable team={data.home_team || "Home"} players={home} />
            <TeamTable team={data.away_team || "Away"} players={away} />
          </div>
        </>
      )}
    </div>
  );
}
