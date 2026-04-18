import { api, type PitchControlResponse } from "@/lib/api";
import PitchHeatmap from "@/components/PitchHeatmap";

export const dynamic = "force-dynamic";

export default async function MetricsPage() {
  let phi: PitchControlResponse | null = null;
  let error: string | null = null;
  try {
    phi = await api<PitchControlResponse>("/api/pitch-control/demo");
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold">Context-aware metrics</h1>
      <p className="mt-2 text-white/60">
        Pitch Control surface from the demo snapshot (11v11, attacking team in
        the final third). Φ(x) ∈ [0, 1] measures the probability that the
        attacking team reaches position x before the defence (Eq. 7).
      </p>

      {error && (
        <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {phi && (
        <div className="mt-8 rounded border border-white/10 bg-white/5 p-4">
          <div className="flex items-center justify-between text-sm">
            <div className="font-medium">Pitch control Φ</div>
            <div className="text-xs text-white/50">
              grid {phi.grid_shape[0]}×{phi.grid_shape[1]} · mean{" "}
              {phi.mean.toFixed(3)}
            </div>
          </div>
          <div className="mt-4">
            <PitchHeatmap phi={phi.phi} x={phi.x} y={phi.y} />
          </div>
          <div className="mt-2 text-xs text-white/50">
            Dark green = defensive dominance (0). Bright green = attacking
            dominance (1).
          </div>
        </div>
      )}
    </div>
  );
}
