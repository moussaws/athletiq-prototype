import {
  api,
  type DDILeaderboardResponse,
  type PitchControlResponse,
} from "@/lib/api";
import PitchHeatmap from "@/components/PitchHeatmap";

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
      <h1 className="text-3xl font-semibold">Context-aware metrics</h1>
      <p className="mt-2 text-white/60">
        Pitch Control surface from the demo snapshot (11v11, attacking team in
        the final third). Φ(x) ∈ [0, 1] measures the probability that the
        attacking team reaches position x before the defence (Eq. 7).
      </p>

      {phiError && (
        <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          {phiError}
        </div>
      )}

      {phi && (
        <div className="mt-8 rounded border border-white/10 bg-white/5 p-4">
          <div className="flex items-center justify-between text-sm">
            <div className="font-medium">Pitch control Φ</div>
            <div className="text-xs text-white/50">
              grid {rows}×{cols} · mean {mean.toFixed(3)}
            </div>
          </div>
          <div className="mt-4">
            <PitchHeatmap phi={phi.phi} xs={phi.xs} ys={phi.ys} />
          </div>
          <div className="mt-2 text-xs text-white/50">
            Dark green = defensive dominance (0). Bright green = attacking
            dominance (1).
          </div>
        </div>
      )}

      <div className="mt-10">
        <h2 className="text-2xl font-semibold">DDI leaderboard</h2>
        <p className="mt-2 text-white/60">
          Per-player Defensive Distortion Index (Eq. 8) — square metres of
          high-threat space (xT ≥ τ) opened up by each attacker over a
          synthetic match. Attribution uses a single-mover scheme: in each of
          the{" "}
          <code className="rounded bg-white/10 px-1">n_actions</code>{" "}
          actions, exactly one attacker steps into the final third; the DDI
          between the before/after pitch-control surfaces is credited to that
          player.
        </p>

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
                  <th className="py-2 pr-2 text-right">DDI (m²)</th>
                  <th className="py-2 pr-2 text-right">Actions</th>
                  <th className="py-2 pr-2 text-right">Avg / action</th>
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
                      <td className="py-2 pr-2 text-right tabular-nums">
                        {row.ddi_m2.toFixed(1)}
                      </td>
                      <td className="py-2 pr-2 text-right tabular-nums text-white/60">
                        {row.actions}
                      </td>
                      <td className="py-2 pr-2 text-right tabular-nums text-white/60">
                        {row.avg_per_action.toFixed(1)}
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
