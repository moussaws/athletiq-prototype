import Link from "next/link";
import { api, type PlayersListResponse } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function PlayersPage({
  searchParams,
}: {
  searchParams: { position?: string; q?: string };
}) {
  const params = new URLSearchParams({ limit: "60" });
  if (searchParams.position) params.set("position", searchParams.position);
  if (searchParams.q) params.set("q", searchParams.q);

  let data: PlayersListResponse | null = null;
  let error: string | null = null;
  try {
    data = await api<PlayersListResponse>(`/api/players?${params.toString()}`);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const positions = ["GK", "CB", "FB", "DM", "CM", "AM", "WG", "ST"];

  return (
    <div className="max-w-6xl">
      <h1 className="font-display text-4xl font-semibold tracking-tightest text-white">Players</h1>
      <p className="mt-2 text-white/60">
        Synthetic cohort generated at API startup. Position-specific archetypes
        with realistic feature distributions.
      </p>

      <form className="mt-6 flex gap-2 text-sm" method="get">
        <input
          name="q"
          defaultValue={searchParams.q ?? ""}
          placeholder="Search by name…"
          className="w-64 rounded border border-white/10 bg-rail px-3 py-1.5 text-white placeholder:text-white/40"
        />
        <select
          name="position"
          defaultValue={searchParams.position ?? ""}
          className="rounded border border-white/10 bg-rail px-3 py-1.5 text-white"
        >
          <option value="">all positions</option>
          {positions.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="rounded bg-accent/20 px-3 py-1.5 text-accent hover:bg-accent/30"
        >
          filter
        </button>
      </form>

      {error && (
        <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          Could not reach the backend API: {error}
          <div className="mt-1 text-white/40">
            Start it with <code>make api</code> (expects{" "}
            <code>http://localhost:8000</code>).
          </div>
        </div>
      )}

      {data && (
        <div className="mt-6 overflow-hidden rounded border border-white/10">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-white/60">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Pos</th>
                <th className="px-4 py-2">Nat</th>
                <th className="px-4 py-2 text-right">Age</th>
                <th className="px-4 py-2 text-right">Value (€M)</th>
                <th className="px-4 py-2 text-right">Foreign</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr key={p.player_id} className="border-t border-white/5">
                  <td className="px-4 py-2">
                    <Link
                      href={`/scouting/${p.player_id}`}
                      className="text-accent hover:underline"
                    >
                      {p.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-white/70">{p.position}</td>
                  <td className="px-4 py-2 text-white/70">{p.nationality}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{p.age}</td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {p.market_value_m.toFixed(1)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {p.is_foreign ? "yes" : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-white/5 bg-white/5 px-4 py-2 text-xs text-white/50">
            {data.items.length} of {data.total} players
          </div>
        </div>
      )}
    </div>
  );
}
