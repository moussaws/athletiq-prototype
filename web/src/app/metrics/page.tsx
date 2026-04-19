import {
  api,
  type DDILeaderboardResponse,
  type PitchControlResponse,
} from "@/lib/api";
import PitchHeatmap from "@/components/PitchHeatmap";
import PitchZonalView from "@/components/PitchZonalView";

export const dynamic = "force-dynamic";

export default async function MetricsPage() {
  let phi: PitchControlResponse | null = null;
  let phiError: string | null = null;
  let lb: DDILeaderboardResponse | null = null;
  let lbError: string | null = null;
  try {
    phi = await api<PitchControlResponse>("/api/pitch-control/demo");
  } catch (e) {
    phiError = e instanceof Error ? e.message : String(e);
  }
  try {
    lb = await api<DDILeaderboardResponse>(
      "/api/metrics/ddi-leaderboard?seed=0&n_actions=60&tau=0.08&limit=11"
    );
  } catch (e) {
    lbError = e instanceof Error ? e.message : String(e);
  }

  const rows = phi?.phi.length ?? 0;
  const cols = phi && rows > 0 ? phi.phi[0].length : 0;
  let mean = 0;
  if (phi && rows > 0 && cols > 0) {
    let sum = 0;
    for (const row of phi.phi) for (const v of row) sum += v;
    mean = sum / (rows * cols);
  }

  const maxDdi = lb ? Math.max(1, ...lb.items.map((r) => r.ddi_m2)) : 1;

  return (
    <div className="max-w-5xl">
      <h1 className="font-display text-4xl font-semibold tracking-tightest text-white">Context-aware metrics</h1>
      <p className="mt-2 text-white/60">
        Where does the attack own the pitch right now? The snapshot below turns
        the pitch-control surface (Eq. 7) into a zonal read: which third, which
        channel, and the single biggest weak spot in each direction.
      </p>

      {phiError && (
        <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          {phiError}
        </div>
      )}

      {phi && phi.zonal && (
        <div className="mt-8">
          <PitchZonalView zonal={phi.zonal} />
        </div>
      )}

      {phi && (
        <details className="mt-4 text-xs text-white/50">
          <summary className="cursor-pointer select-none text-white/60">
            Analyst view — raw 34×52 grid
          </summary>
          <div className="mt-3 rounded border border-white/10 bg-white/5 p-4">
            <div className="flex items-center justify-between text-sm">
              <div className="font-medium text-white/80">Pitch control Φ</div>
              <div className="text-xs text-white/50">
                grid {rows}×{cols} · mean {mean.toFixed(3)}
              </div>
            </div>
            <div className="mt-4">
              <PitchHeatmap phi={phi.phi} xs={phi.xs} ys={phi.ys} />
            </div>
            <p className="mt-2 text-xs text-white/50">
              Φ(x) ∈ [0, 1] — probability that the attacking team reaches
              position x before the defence. Dark green = defensive dominance
              (0). Bright green = attacking dominance (1).
            </p>
          </div>
        </details>
      )}

      <div className="mt-10">
        <h2 className="text-2xl font-semibold">Who opens up the final third?</h2>
        <p className="mt-2 text-white/70">
          A ranking of the players who, by stepping in with the ball, created
          the most <span className="text-white">dangerous space</span> for
          team-mates — the area inside the opposition&apos;s final-third defensive
          shape that suddenly became attackable.
        </p>
        {lb && (
          <p className="mt-2 rounded border border-accent/30 bg-accent/5 p-3 text-sm text-white/90">
            {lb.headline}
          </p>
        )}
        <details className="mt-2 text-xs text-white/40">
          <summary className="cursor-pointer select-none">Analyst view</summary>
          <p className="mt-1">
            Defensive Distortion Index (Eq. 8) — square metres of high-threat
            space (xT ≥ τ) opened up by each attacker over a synthetic match.
            Single-mover attribution: in each of the{" "}
            <code className="rounded bg-white/10 px-1">n_actions</code>{" "}
            actions, exactly one attacker steps into the final third; the DDI
            between the before/after pitch-control surfaces is credited to that
            player.
          </p>
        </details>

        {lbError && (
          <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
            {lbError}
          </div>
        )}

        {lb && (
          <div className="mt-6 rounded border border-white/10 bg-white/5 p-4">
            <div className="flex items-center justify-between text-xs text-white/50">
              <div>
                seed {lb.seed} · {lb.n_actions} actions · τ = {lb.tau}
              </div>
              <div>
                total high-threat space created ={" "}
                <span className="text-white">
                  {lb.total_ddi_m2.toFixed(1)} m²
                </span>
              </div>
            </div>
            <table className="mt-4 w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-left text-xs uppercase text-white/50">
                  <th className="py-2 pr-2">#</th>
                  <th className="py-2 pr-2">Player</th>
                  <th className="py-2 pr-2">Pos</th>
                  <th className="py-2 pr-2">Coach verdict</th>
                  <th className="py-2 pr-2 text-right">Space (m²)</th>
                  <th className="py-2 pr-2">Share</th>
                </tr>
              </thead>
              <tbody>
                {lb.items.map((row, i) => {
                  const share = maxDdi > 0 ? row.ddi_m2 / maxDdi : 0;
                  return (
                    <tr
                      key={row.player_id}
                      className="border-b border-white/5 last:border-0"
                    >
                      <td className="py-2 pr-2 text-white/40">{i + 1}</td>
                      <td className="py-2 pr-2 font-medium">{row.name}</td>
                      <td className="py-2 pr-2 text-white/60">
                        {row.position}
                      </td>
                      <td className="py-2 pr-2 text-white/80">
                        {row.verdict}
                      </td>
                      <td className="py-2 pr-2 text-right tabular-nums">
                        {row.ddi_m2.toFixed(1)}
                      </td>
                      <td className="py-2 pr-2">
                        <div className="h-2 w-full rounded bg-white/10">
                          <div
                            className="h-2 rounded bg-accent"
                            style={{
                              width: `${Math.max(1, Math.round(share * 100))}%`,
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="mt-3 text-xs text-white/40">
              Synthetic 4-3-3 vs 4-4-2. Zero-DDI rows mean the player never
              reached the high-xT region (τ = {lb.tau}) in their simulated
              actions — typical for centre-backs and goalkeepers.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
