"use client";

import { useEffect, useState } from "react";
import {
  api,
  type AhpPreference,
  type AhpResponse,
  type SavedSquad,
  type SquadResponse,
} from "@/lib/api";

const DEFAULT_CRITERIA = [
  "pabr",
  "xt_carry",
  "ddi",
  "interceptions",
  "passes_completed",
];

const SAATY_SCALE = [
  { value: 1, label: "equal" },
  { value: 3, label: "moderate" },
  { value: 5, label: "strong" },
  { value: 7, label: "very strong" },
  { value: 9, label: "extreme" },
];

const DEFAULT_FORMATION = {
  GK: 1,
  CB: 2,
  FB: 2,
  DM: 1,
  CM: 2,
  AM: 1,
  WG: 1,
  ST: 1,
};

function makeAllOnes(n: number): number[][] {
  return Array.from({ length: n }, () => Array.from({ length: n }, () => 1));
}

export default function SquadPage() {
  const [criteria, setCriteria] = useState<string[]>(DEFAULT_CRITERIA);
  const [matrix, setMatrix] = useState<number[][]>(() =>
    makeAllOnes(DEFAULT_CRITERIA.length),
  );
  const [ahp, setAhp] = useState<AhpResponse | null>(null);
  const [squad, setSquad] = useState<SquadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [budget, setBudget] = useState(800);
  const [foreignMax, setForeignMax] = useState(6);

  const [prefs, setPrefs] = useState<AhpPreference[]>([]);
  const [savedSquads, setSavedSquads] = useState<SavedSquad[]>([]);
  const [prefName, setPrefName] = useState("");
  const [squadName, setSquadName] = useState("");
  const [loadedPrefId, setLoadedPrefId] = useState<number | null>(null);

  const refreshSaved = async () => {
    try {
      const [p, s] = await Promise.all([
        api<AhpPreference[]>("/api/squad/preferences"),
        api<SavedSquad[]>("/api/squad/saved"),
      ]);
      setPrefs(p);
      setSavedSquads(s);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    void refreshSaved();
  }, []);

  const setCell = (i: number, j: number, val: number) => {
    setMatrix((m) =>
      m.map((row, ri) =>
        row.map((cell, ci) => {
          if (ri === i && ci === j) return val;
          if (ri === j && ci === i) return 1 / val;
          return cell;
        }),
      ),
    );
  };

  const onOptimize = async () => {
    setBusy(true);
    setError(null);
    setAhp(null);
    setSquad(null);
    try {
      const ahpRes = await api<AhpResponse>("/api/squad/ahp", {
        method: "POST",
        body: JSON.stringify({ criteria, pairwise_matrix: matrix }),
      });
      setAhp(ahpRes);
      const squadRes = await api<SquadResponse>("/api/squad", {
        method: "POST",
        body: JSON.stringify({
          criteria,
          weights: ahpRes.weights,
          formation: DEFAULT_FORMATION,
          budget,
          foreign_max: foreignMax,
        }),
      });
      setSquad(squadRes);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSavePref = async () => {
    if (!ahp || !prefName.trim()) return;
    try {
      const created = await api<AhpPreference>("/api/squad/preferences", {
        method: "POST",
        body: JSON.stringify({
          name: prefName.trim(),
          criteria,
          pairwise_matrix: matrix,
          weights: ahp.weights,
          consistency_ratio: ahp.consistency_ratio,
          is_consistent: ahp.is_consistent,
        }),
      });
      setLoadedPrefId(created.id);
      setPrefName("");
      await refreshSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onLoadPref = (p: AhpPreference) => {
    setCriteria(p.criteria);
    setMatrix(p.pairwise_matrix.map((row) => [...row]));
    setAhp({
      criteria: p.criteria,
      weights: p.weights,
      consistency_ratio: p.consistency_ratio,
      is_consistent: p.is_consistent,
    });
    setSquad(null);
    setLoadedPrefId(p.id);
  };

  const onDeletePref = async (id: number) => {
    try {
      await api(`/api/squad/preferences/${id}`, { method: "DELETE" });
      if (loadedPrefId === id) setLoadedPrefId(null);
      await refreshSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onSaveSquad = async () => {
    if (!squad || !ahp || !squadName.trim()) return;
    try {
      await api<SavedSquad>("/api/squad/saved", {
        method: "POST",
        body: JSON.stringify({
          name: squadName.trim(),
          preference_id: loadedPrefId,
          criteria,
          weights: ahp.weights,
          formation: DEFAULT_FORMATION,
          budget,
          foreign_max: foreignMax,
          assignments: squad.assignments,
          total_score: squad.total_score,
          squad_gap_position: squad.squad_gap_position,
          squad_gap_delta: squad.squad_gap_delta,
          budget_used: squad.budget_used,
          foreign_count: squad.foreign_count,
        }),
      });
      setSquadName("");
      await refreshSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onLoadSquad = (s: SavedSquad) => {
    setCriteria(s.criteria);
    setMatrix(makeAllOnes(s.criteria.length));
    setBudget(s.budget);
    setForeignMax(s.foreign_max);
    setSquad({
      assignments: s.assignments,
      total_score: s.total_score,
      squad_gap_position: s.squad_gap_position,
      squad_gap_delta: s.squad_gap_delta,
      budget_used: s.budget_used,
      foreign_count: s.foreign_count,
    });
    setAhp({
      criteria: s.criteria,
      weights: s.weights,
      consistency_ratio: 0,
      is_consistent: true,
    });
    if (s.preference_id != null) setLoadedPrefId(s.preference_id);
  };

  const onDeleteSquad = async (id: number) => {
    try {
      await api(`/api/squad/saved/${id}`, { method: "DELETE" });
      await refreshSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="grid max-w-6xl gap-8 lg:grid-cols-[1fr_280px]">
      <div>
        <h1 className="text-3xl font-semibold">Squad optimizer</h1>
        <p className="mt-2 text-white/60">
          Build an AHP pairwise matrix for your criteria, let the engine
          compute weights + consistency ratio, then solve the BIP roster
          optimization (Eq. 12–18) for the optimal XI. Save your preferences
          and resulting XIs to re-load them later.
        </p>

        <h2 className="mt-8 text-sm font-medium text-white/80">
          AHP pairwise preferences
        </h2>
        <p className="mt-1 text-xs text-white/50">
          For each pair, how strongly does row dominate column? 1=equal,
          3=moderate, 5=strong, 7=very strong, 9=extreme. Reciprocals
          auto-fill.
        </p>
        <div className="mt-4 overflow-x-auto rounded border border-white/10">
          <table className="min-w-full text-sm">
            <thead className="bg-white/5 text-left text-white/60">
              <tr>
                <th className="px-3 py-2"></th>
                {criteria.map((c) => (
                  <th key={c} className="px-3 py-2">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {criteria.map((rowC, i) => (
                <tr key={rowC} className="border-t border-white/5">
                  <td className="px-3 py-2 font-medium">{rowC}</td>
                  {criteria.map((colC, j) => {
                    if (i === j) {
                      return (
                        <td key={colC} className="px-3 py-2 text-white/40">
                          1
                        </td>
                      );
                    }
                    if (i > j) {
                      return (
                        <td key={colC} className="px-3 py-2 text-white/40">
                          {matrix[i][j].toFixed(2)}
                        </td>
                      );
                    }
                    return (
                      <td key={colC} className="px-3 py-2">
                        <select
                          className="rounded border border-white/10 bg-rail px-2 py-1 text-xs"
                          value={matrix[i][j]}
                          onChange={(e) =>
                            setCell(i, j, parseFloat(e.target.value))
                          }
                        >
                          {SAATY_SCALE.map((s) => (
                            <option key={s.value} value={s.value}>
                              {s.value}× {s.label}
                            </option>
                          ))}
                        </select>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-6 flex flex-wrap items-end gap-4 text-sm">
          <label className="flex flex-col">
            <span className="text-xs text-white/60">Budget (€M)</span>
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(parseFloat(e.target.value))}
              className="w-32 rounded border border-white/10 bg-rail px-2 py-1"
            />
          </label>
          <label className="flex flex-col">
            <span className="text-xs text-white/60">Foreign max</span>
            <input
              type="number"
              value={foreignMax}
              onChange={(e) => setForeignMax(parseInt(e.target.value, 10))}
              className="w-24 rounded border border-white/10 bg-rail px-2 py-1"
            />
          </label>
          <button
            type="button"
            onClick={onOptimize}
            disabled={busy}
            className="rounded bg-accent/20 px-4 py-2 font-medium text-accent hover:bg-accent/30 disabled:opacity-50"
          >
            {busy ? "solving…" : "Compute weights & optimize squad"}
          </button>
        </div>

        {error && (
          <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
            {error}
          </div>
        )}

        {ahp && (
          <div className="mt-8 rounded border border-white/10 bg-white/5 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-medium">AHP weights</div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="preference name"
                  value={prefName}
                  onChange={(e) => setPrefName(e.target.value)}
                  className="w-44 rounded border border-white/10 bg-rail px-2 py-1 text-xs"
                />
                <button
                  type="button"
                  onClick={onSavePref}
                  disabled={!prefName.trim()}
                  className="rounded bg-accent/20 px-3 py-1 text-xs font-medium text-accent hover:bg-accent/30 disabled:opacity-40"
                >
                  Save preference
                </button>
              </div>
            </div>
            <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
              {criteria.map((c, i) => (
                <div key={c} className="flex items-center gap-3 text-sm">
                  <span className="w-32 text-white/60">{c}</span>
                  <div className="h-2 flex-1 rounded bg-white/10">
                    <div
                      className="h-2 rounded bg-accent"
                      style={{ width: `${Math.round(ahp.weights[i] * 100)}%` }}
                    />
                  </div>
                  <span className="w-14 text-right tabular-nums">
                    {(ahp.weights[i] * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-3 text-xs text-white/50">
              CR = {ahp.consistency_ratio.toFixed(3)} (
              {ahp.is_consistent ? "consistent" : "INCONSISTENT — revise"})
            </div>
          </div>
        )}

        {squad && (
          <div className="mt-6 rounded border border-white/10 bg-white/5 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm font-medium">Optimal XI</div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="squad name"
                  value={squadName}
                  onChange={(e) => setSquadName(e.target.value)}
                  className="w-44 rounded border border-white/10 bg-rail px-2 py-1 text-xs"
                />
                <button
                  type="button"
                  onClick={onSaveSquad}
                  disabled={!squadName.trim()}
                  className="rounded bg-accent/20 px-3 py-1 text-xs font-medium text-accent hover:bg-accent/30 disabled:opacity-40"
                >
                  Save squad
                </button>
              </div>
            </div>
            <div className="mt-2 text-xs text-white/50">
              Q = {squad.total_score.toFixed(3)} · €
              {squad.budget_used.toFixed(1)}M used · {squad.foreign_count}{" "}
              foreigners
              {squad.squad_gap_position && (
                <>
                  {" "}
                  · gap:{" "}
                  <span className="text-accent">
                    {squad.squad_gap_position}
                  </span>{" "}
                  (Δ{squad.squad_gap_delta.toFixed(3)})
                </>
              )}
            </div>
            <table className="mt-3 w-full text-sm">
              <thead className="text-left text-white/60">
                <tr>
                  <th className="py-1">Pos</th>
                  <th className="py-1">Player</th>
                  <th className="py-1 text-right">Score</th>
                  <th className="py-1 text-right">Value (€M)</th>
                  <th className="py-1 text-right">Foreign</th>
                </tr>
              </thead>
              <tbody>
                {squad.assignments.map((p) => (
                  <tr key={p.player_id} className="border-t border-white/5">
                    <td className="py-1.5 text-white/70">{p.position}</td>
                    <td className="py-1.5">{p.name}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      {p.positional_fit.toFixed(3)}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">
                      {p.market_value_m.toFixed(1)}
                    </td>
                    <td className="py-1.5 text-right">
                      {p.is_foreign ? "yes" : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <aside className="space-y-6">
        <div className="rounded border border-white/10 bg-white/5 p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">Saved preferences</div>
            <div className="text-xs text-white/40">{prefs.length}</div>
          </div>
          {prefs.length === 0 ? (
            <div className="mt-2 text-xs text-white/40">
              Compute weights and save one to re-load later.
            </div>
          ) : (
            <ul className="mt-2 space-y-1">
              {prefs.map((p) => (
                <li
                  key={p.id}
                  className={`flex items-center justify-between gap-2 rounded px-2 py-1 text-xs ${
                    loadedPrefId === p.id
                      ? "bg-accent/10 text-accent"
                      : "text-white/80 hover:bg-white/5"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => onLoadPref(p)}
                    className="flex-1 truncate text-left"
                  >
                    {p.name}
                    <span className="ml-1 text-white/40">
                      CR {p.consistency_ratio.toFixed(2)}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeletePref(p.id)}
                    className="text-white/40 hover:text-red-400"
                    aria-label="delete"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded border border-white/10 bg-white/5 p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">Saved squads</div>
            <div className="text-xs text-white/40">{savedSquads.length}</div>
          </div>
          {savedSquads.length === 0 ? (
            <div className="mt-2 text-xs text-white/40">
              Solve an XI and save it to compare alternatives.
            </div>
          ) : (
            <ul className="mt-2 space-y-1">
              {savedSquads.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center justify-between gap-2 rounded px-2 py-1 text-xs text-white/80 hover:bg-white/5"
                >
                  <button
                    type="button"
                    onClick={() => onLoadSquad(s)}
                    className="flex-1 truncate text-left"
                  >
                    {s.name}
                    <span className="ml-1 text-white/40">
                      Q {s.total_score.toFixed(2)}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteSquad(s.id)}
                    className="text-white/40 hover:text-red-400"
                    aria-label="delete"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
