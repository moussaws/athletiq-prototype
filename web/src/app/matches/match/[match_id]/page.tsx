import Link from "next/link";
import {
  api,
  type MatchNarrativeResponse,
  type StatsBombMatchCohortResponse,
  type StatsBombMatchPlayer,
  type TeamSummary,
  type TopPerformer,
} from "@/lib/api";
import { VAEPPanel } from "./VAEPPanel";

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

function TeamCard({ team }: { team: TeamSummary }) {
  return (
    <div className="flex-1 rounded border border-white/10 bg-white/[0.02] p-4">
      <div className="flex items-baseline justify-between">
        <div className="text-lg font-semibold">{team.team}</div>
        <div className="text-xs text-white/50">{team.players_count} players</div>
      </div>
      <p className="mt-2 text-sm text-white/80">{team.summary}</p>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
        <Stat label="xT carry" value={team.total_xt_carry.toFixed(2)} accent />
        <Stat label="Shots" value={team.total_shots.toFixed(0)} />
        <Stat label="Take-ons" value={team.total_take_ons.toFixed(0)} />
        <Stat label="Passes" value={team.total_passes.toFixed(0)} />
        <Stat
          label="Tackles+Int"
          value={team.total_defensive_actions.toFixed(0)}
        />
      </div>

      {team.top_performers.length > 0 && (
        <div className="mt-5">
          <div className="text-xs font-medium uppercase tracking-wide text-white/50">
            Top performers
          </div>
          <ul className="mt-2 space-y-2">
            {team.top_performers.map((p) => (
              <PerformerRow key={p.role + p.player_id} p={p} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded bg-white/5 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-white/50">
        {label}
      </div>
      <div
        className={
          "text-sm font-medium tabular-nums " + (accent ? "text-accent" : "")
        }
      >
        {value}
      </div>
    </div>
  );
}

function PerformerRow({ p }: { p: TopPerformer }) {
  return (
    <li className="flex items-start gap-3 rounded border border-white/5 bg-white/[0.02] px-3 py-2">
      <span className="mt-0.5 rounded bg-accent/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent">
        {p.role}
      </span>
      <div className="flex-1">
        <div className="text-sm">
          <span className="font-medium">{p.name}</span>
          <span className="ml-2 text-xs text-white/60">{p.position}</span>
        </div>
        <p className="mt-0.5 text-xs text-white/70">{p.verdict}</p>
      </div>
    </li>
  );
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
  let narrative: MatchNarrativeResponse | null = null;
  let cohort: StatsBombMatchCohortResponse | null = null;
  let error: string | null = null;
  try {
    [narrative, cohort] = await Promise.all([
      api<MatchNarrativeResponse>(
        `/api/statsbomb/match/${params.match_id}/insights`,
      ),
      api<StatsBombMatchCohortResponse>(
        `/api/statsbomb/match/${params.match_id}`,
      ),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const home: StatsBombMatchPlayer[] = [];
  const away: StatsBombMatchPlayer[] = [];
  if (cohort) {
    for (const p of cohort.players) {
      if (p.team === cohort.home_team) home.push(p);
      else if (p.team === cohort.away_team) away.push(p);
      else home.push(p);
    }
  }

  return (
    <div className="max-w-6xl">
      <Link href="/matches" className="text-sm text-accent hover:underline">
        ← back to competitions
      </Link>

      <h1 className="mt-4 text-3xl font-semibold">
        {narrative
          ? `${narrative.home_team || "Home"} vs ${narrative.away_team || "Away"}`
          : `Match ${params.match_id}`}
      </h1>
      {narrative && (
        <p className="mt-1 text-white/60">
          <span className="text-accent">{narrative.score || "—"}</span>
          <span className="ml-2 text-xs">· match id {narrative.match_id}</span>
        </p>
      )}

      {error && (
        <div className="mt-4 rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {narrative && (
        <>
          <div className="mt-6 rounded border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-100">
            <span className="font-medium">Coach headline.</span>{" "}
            {narrative.headline}
          </div>

          <h2 className="mt-8 text-lg font-semibold">Team breakdown</h2>
          <p className="mt-1 text-sm text-white/60">
            What each side contributed, and who drove it.
          </p>
          <div className="mt-4 flex flex-col gap-6 lg:flex-row">
            {narrative.teams.map((t) => (
              <TeamCard key={t.team} team={t} />
            ))}
          </div>

          <VAEPPanel matchId={params.match_id} />

          <details className="mt-8 rounded border border-white/10 bg-white/[0.02] p-4">
            <summary className="cursor-pointer select-none text-sm font-medium text-white/80">
              Analyst view · raw per-player event totals
            </summary>
            <div className="mt-3 rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/90">
              <span className="font-medium">Data coverage.</span>{" "}
              StatsBomb open data provides event streams but not
              high-frequency tracking, so the AthletIQ indices that need
              tracking (
              <code>{narrative.imputed_features.join(", ")}</code>) are
              imputed to position means downstream. Event-derived features
              (passes, take-ons, shots, tackles, interceptions, xT carry)
              are observed directly from this match.
            </div>
            {cohort && (
              <div className="mt-4 flex flex-col gap-6 lg:flex-row">
                <TeamTable
                  team={cohort.home_team || "Home"}
                  players={home}
                />
                <TeamTable
                  team={cohort.away_team || "Away"}
                  players={away}
                />
              </div>
            )}
          </details>
        </>
      )}
    </div>
  );
}
