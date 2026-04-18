"use client";

import { useState } from "react";
import { API_BASE } from "@/lib/api";

type PlayerVAEP = {
  player_id: string;
  name: string;
  team: string;
  position: string;
  n_actions: number;
  vaep: number;
  offensive_vaep: number;
  defensive_vaep: number;
};

type MatchVAEPResponse = {
  match_id: number;
  k_horizon: number;
  n_actions: number;
  n_goals: number;
  players: PlayerVAEP[];
  verdict: string;
};

export function VAEPPanel({ matchId }: { matchId: string }) {
  const [data, setData] = useState<MatchVAEPResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/vaep/match/${matchId}`);
      if (!r.ok) throw new Error(await r.text());
      setData(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-8 rounded border border-white/10 bg-white/[0.02] p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Action value · VAEP-lite</h2>
          <p className="mt-1 text-sm text-white/60">
            Who added the most scoring-probability per on-ball action. Fits a
            logistic action-value model on this match&apos;s events (goal
            within 10 actions) and attributes the per-action ΔP to the player
            performing it.
          </p>
        </div>
        <button
          onClick={run}
          disabled={busy}
          className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-black hover:bg-accent/90 disabled:opacity-50"
        >
          {busy ? "Fitting…" : data ? "Re-run" : "Compute"}
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {data && (
        <div className="mt-4 space-y-4">
          <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
            <span className="font-medium">Readout.</span> {data.verdict}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <Stat label="actions" value={data.n_actions.toFixed(0)} />
            <Stat label="goals in match" value={data.n_goals.toFixed(0)} />
            <Stat label="horizon K" value={`${data.k_horizon} actions`} />
            <Stat label="players scored" value={data.players.length.toFixed(0)} />
          </div>

          <div className="overflow-hidden rounded border border-white/10">
            <table className="w-full text-xs">
              <thead className="bg-white/5 text-left text-white/60">
                <tr>
                  <th className="px-3 py-2">#</th>
                  <th className="px-3 py-2">Player</th>
                  <th className="px-3 py-2">Team</th>
                  <th className="px-3 py-2">Pos</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                  <th className="px-3 py-2 text-right">Offensive</th>
                  <th className="px-3 py-2 text-right">Defensive</th>
                  <th className="px-3 py-2 text-right">VAEP-lite</th>
                </tr>
              </thead>
              <tbody>
                {data.players.slice(0, 12).map((p, i) => (
                  <tr key={p.player_id} className="border-t border-white/5">
                    <td className="px-3 py-1.5 text-white/60">{i + 1}</td>
                    <td className="px-3 py-1.5">{p.name}</td>
                    <td className="px-3 py-1.5 text-white/70">{p.team}</td>
                    <td className="px-3 py-1.5 text-white/70">{p.position}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {p.n_actions}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {p.offensive_vaep >= 0 ? "+" : ""}
                      {p.offensive_vaep.toFixed(3)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {p.defensive_vaep >= 0 ? "+" : ""}
                      {p.defensive_vaep.toFixed(3)}
                    </td>
                    <td className="px-3 py-1.5 text-right font-medium tabular-nums text-accent">
                      {p.vaep >= 0 ? "+" : ""}
                      {p.vaep.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-[11px] text-white/40">
            Lite variant: the model is fit on this match&apos;s own events
            (~{data.n_actions} actions), so coefficients calibrate the local
            action value rather than a population prior. With {data.n_goals}{" "}
            goals in the sample, rankings are suggestive, not definitive.
          </p>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-white/5 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-white/50">
        {label}
      </div>
      <div className="text-sm font-medium tabular-nums">{value}</div>
    </div>
  );
}
