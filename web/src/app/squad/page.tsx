"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  api,
  type AhpPreference,
  type AhpResponse,
  type SavedSquad,
  type SquadResponse,
} from "@/lib/api";
import {
  SQUAD_PHILOSOPHIES,
  type SquadPhilosophy,
  type SquadPhilosophyKey,
} from "@/lib/squad-presets";

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

function PresetFromUrl({
  onPreset,
}: {
  onPreset: (key: SquadPhilosophyKey) => void;
}) {
  const searchParams = useSearchParams();
  const applied = useRef(false);
  useEffect(() => {
    if (applied.current) return;
    const key = searchParams.get("preset") as SquadPhilosophyKey | null;
    if (!key) return;
    applied.current = true;
    onPreset(key);
  }, [searchParams, onPreset]);
  return null;
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
  const [activePhilosophy, setActivePhilosophy] =
    useState<SquadPhilosophyKey | null>(null);

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

  const handlePresetFromUrl = (key: SquadPhilosophyKey) => {
    const p = SQUAD_PHILOSOPHIES.find((s) => s.key === key);
    if (p) void onApplyPhilosophy(p);
  };

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

  const runOptimize = async (
    useCriteria: string[],
    useMatrix: number[][],
  ) => {
    setBusy(true);
    setError(null);
    setAhp(null);
    setSquad(null);
    try {
      const ahpRes = await api<AhpResponse>("/api/squad/ahp", {
        method: "POST",
        body: JSON.stringify({
          criteria: useCriteria,
          pairwise_matrix: useMatrix,
        }),
      });
      setAhp(ahpRes);
      const squadRes = await api<SquadResponse>("/api/squad", {
        method: "POST",
        body: JSON.stringify({
          criteria: useCriteria,
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

  const onOptimize = () => runOptimize(criteria, matrix);

  const onApplyPhilosophy = async (p: SquadPhilosophy) => {
    const cloned = p.matrix.map((row) => [...row]);
    setCriteria(p.criteria);
    setMatrix(cloned);
    setActivePhilosophy(p.key);
    setLoadedPrefId(null);
    await runOptimize(p.criteria, cloned);
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
    setActivePhilosophy(null);
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
    setLoadedPrefId(s.preference_id);
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
      <Suspense fallback={null}>
        <PresetFromUrl onPreset={handlePresetFromUrl} />
      </Suspense>
      <div>
        <h1 className="text-3xl font-semibold">Squad optimizer</h1>
        <p className="mt-2 text-white/60">
          Pick your footballing philosophy and we&apos;ll weight the criteria
          for you, solve the roster optimization, and name the XI. The raw AHP
          pairwise matrix is one click away if you want to tune it yourself.
        </p>

        <h2 className="mt-8 text-sm font-medium text-white/80">
          Your philosophy
        </h2>
        <p className="mt-1 text-xs text-white/50">
          Pick the style you want this team to play. You can always tweak the
          weights by opening the Analyst view below.
        </p>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          {SQUAD_PHILOSOPHIES.map((p) => {
            const active = activePhilosophy === p.key;
            return (
              <button
                key={p.key}
                type="button"
                onClick={() => void onApplyPhilosophy(p)}
                disabled={busy}
                className={`rounded-lg border p-4 text-left transition disabled:opacity-60 ${
                  active
                    ? "border-accent bg-accent/10"
                    : "border-white/10 bg-white/5 hover:border-white/30"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">{p.label}</div>
                  {active && (
                    <span className="rounded bg-accent/20 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-accent">
                      active
                    </span>
                  )}
                </div>
                <div className="mt-1 text-xs text-white/60">{p.tagline}</div>
                <div className="mt-2 text-xs text-white/50">{p.summary}</div>
              </button>
            );
          })}
        </div>

        <details className="mt-6 rounded border border-white/10 bg-white/5">
          <summary className="cursor-pointer list-none px-4 py-3 text-xs font-medium text-white/70 hover:text-white">
            Analyst view — edit the AHP pairwise matrix directly
          </summary>
          <div className="border-t border-white/10 p-4">
            <p className="text-xs text-white/50">
              For each pair, how strongly does row dominate column? 1=equal,
              3=moderate, 5=strong, 7=very strong, 9=extreme. Reciprocals
              auto-fill. Editing a cell clears the active philosophy so you
              know the matrix is now custom.
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
                              onChange={(e) => {
                                setCell(i, j, parseFloat(e.target.value));
                                setActivePhilosophy(null);
                              }}
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
          </div>
        </details>

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
            {busy
              ? "solving…"
              : activePhilosophy
                ? "Re-optimize with current budget / caps"
                : "Compute weights & optimize squad"}
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
