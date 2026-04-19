"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import ScenarioDiffCards from "@/components/ScenarioDiffCards";
import ScenarioHeadline from "@/components/ScenarioHeadline";
import ScenarioPitch from "@/components/ScenarioPitch";
import {
  API_BASE,
  VALID_FORMATIONS,
  type Formation,
  type FormationPresetResponse,
  type Point,
  type ScenarioResponse,
} from "@/lib/api";

type ScenarioState = {
  attackers: Point[];
  defenders: Point[];
  ball: Point;
};

const PITCH_LENGTH = 105;
const DEFAULT_GRID = { grid_rows: 34, grid_cols: 52 };

async function fetchPreset(
  formation: Formation,
  role: "attacker" | "defender",
  signal?: AbortSignal,
): Promise<FormationPresetResponse> {
  const r = await fetch(
    `${API_BASE}/api/pitch-control/scenario/preset?formation=${encodeURIComponent(
      formation,
    )}&role=${role}`,
    { cache: "no-store", signal },
  );
  if (!r.ok) throw new Error(`preset ${formation}/${role} failed: ${r.status}`);
  return (await r.json()) as FormationPresetResponse;
}

async function postScenario(
  state: ScenarioState,
  baseline: ScenarioState | null,
  signal?: AbortSignal,
): Promise<ScenarioResponse> {
  const body: Record<string, unknown> = { ...state, ...DEFAULT_GRID };
  if (baseline) body.baseline = baseline;
  const r = await fetch(`${API_BASE}/api/pitch-control/scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
    signal,
  });
  if (!r.ok) throw new Error(`scenario POST failed: ${r.status}`);
  return (await r.json()) as ScenarioResponse;
}

/**
 * Shift the whole defender block by ``delta`` metres along the x-axis
 * (attacker attacks +x, so negative delta pushes the defence toward the
 * attacker's goal = pressing higher; positive delta drops the block).
 */
function shiftDefenderLine(defenders: Point[], delta: number): Point[] {
  return defenders.map((p) => ({
    x: Math.max(0, Math.min(PITCH_LENGTH, p.x + delta)),
    y: p.y,
  }));
}

export default function ScenarioLab() {
  const [formation, setFormation] = useState<Formation>("4-3-3");
  const [baseline, setBaseline] = useState<ScenarioState | null>(null);
  const [state, setState] = useState<ScenarioState | null>(null);
  const [phi, setPhi] = useState<ScenarioResponse | null>(null);
  // Remember the initial Φ that belongs to the baseline so the diff cards
  // can show "baseline → current" values after the first edit.
  const [baselinePhi, setBaselinePhi] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lineNudge, setLineNudge] = useState(0); // metres
  const [lastElapsed, setLastElapsed] = useState<number | null>(null);

  // abort the in-flight POST when a new drag commits
  const inflight = useRef<AbortController | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // monotonically-increasing generation so an aborted request's `.finally`
  // doesn't prematurely clear `recomputing` for its replacement.
  const generation = useRef(0);

  // Load preset → establish baseline + initial Φ.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const [atk, dfn] = await Promise.all([
          fetchPreset(formation, "attacker"),
          fetchPreset(formation, "defender"),
        ]);
        const init: ScenarioState = {
          attackers: atk.positions,
          defenders: dfn.positions,
          ball: atk.ball,
        };
        // Initial load: no baseline field, so `resp.diff` stays null.
        const resp = await postScenario(init, null);
        if (cancelled) return;
        setBaseline(init);
        setState(init);
        setPhi(resp);
        setBaselinePhi(resp);
        setLineNudge(0);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      // Cancel any pending debounced recompute and abort the in-flight POST
      // so a stale old-formation response can't race past the guard and
      // overwrite the new formation's Φ after it loads.
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
        debounceTimer.current = null;
      }
      inflight.current?.abort();
      // Bump the generation too so any already-resolving predecessor is
      // strictly ignored by the `generation.current === gen` guards below.
      generation.current += 1;
    };
  }, [formation]);

  // Debounced recompute on state change. Every request after the initial
  // load pins the current baseline so the backend returns a proper diff.
  const scheduleRecompute = useCallback((next: ScenarioState, base: ScenarioState) => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      inflight.current?.abort();
      const ctrl = new AbortController();
      inflight.current = ctrl;
      const gen = ++generation.current;
      setRecomputing(true);
      const t0 = performance.now();
      postScenario(next, base, ctrl.signal)
        .then((resp) => {
          if (generation.current !== gen) return;
          setPhi(resp);
          setLastElapsed(performance.now() - t0);
        })
        .catch((e) => {
          if ((e as Error).name === "AbortError") return;
          if (generation.current !== gen) return;
          setError(e instanceof Error ? e.message : String(e));
        })
        .finally(() => {
          // Only the latest request's completion clears the spinner; aborted
          // predecessors leave `recomputing=true` for their replacement.
          if (generation.current === gen) setRecomputing(false);
        });
    }, 120);
  }, []);

  function applyPatch(next: ScenarioState) {
    if (!baseline) return;
    setState(next);
    scheduleRecompute(next, baseline);
  }

  function onReset() {
    if (!baseline) return;
    setState(baseline);
    setLineNudge(0);
    scheduleRecompute(baseline, baseline);
  }

  function onLineNudge(newDelta: number) {
    if (!state || !baseline) return;
    const shift = newDelta - lineNudge;
    const nextDef = shiftDefenderLine(state.defenders, shift);
    setLineNudge(newDelta);
    applyPatch({ ...state, defenders: nextDef });
  }

  // Whole-pitch & final-third Φ means are derived from the grid so we
  // don't need a second endpoint call just for the diff-card values.
  const phiStats = useCallback((resp: ScenarioResponse | null) => {
    if (!resp) {
      return { phi_mean: 0, phi_final_third: 0 };
    }
    const grid = resp.phi;
    const xs = resp.xs;
    let total = 0;
    let count = 0;
    let ftTotal = 0;
    let ftCount = 0;
    for (let r = 0; r < grid.length; r++) {
      const row = grid[r];
      for (let c = 0; c < row.length; c++) {
        total += row[c];
        count += 1;
        if (xs[c] >= 70) {
          ftTotal += row[c];
          ftCount += 1;
        }
      }
    }
    return {
      phi_mean: count ? total / count : 0,
      phi_final_third: ftCount ? ftTotal / ftCount : 0,
    };
  }, []);

  const baselineSnapshot = useMemo(() => {
    const stats = phiStats(baselinePhi);
    return {
      phi_mean: stats.phi_mean,
      phi_final_third: stats.phi_final_third,
      balance_attacker_pct: baselinePhi?.zonal?.balance_attacker_pct ?? 50,
      defensive_line_height_m: baselinePhi?.defensive_line_height_m ?? 0,
    };
  }, [baselinePhi, phiStats]);

  const currentSnapshot = useMemo(() => {
    const stats = phiStats(phi);
    return {
      phi_mean: stats.phi_mean,
      phi_final_third: stats.phi_final_third,
      balance_attacker_pct: phi?.zonal?.balance_attacker_pct ?? 50,
      defensive_line_height_m: phi?.defensive_line_height_m ?? 0,
    };
  }, [phi, phiStats]);

  const edited = useMemo(() => {
    if (!state || !baseline) return false;
    if (lineNudge !== 0) return true;
    const same = (a: Point[], b: Point[]) =>
      a.length === b.length &&
      a.every((p, i) => p.x === b[i].x && p.y === b[i].y);
    return (
      !same(state.attackers, baseline.attackers) ||
      !same(state.defenders, baseline.defenders) ||
      state.ball.x !== baseline.ball.x ||
      state.ball.y !== baseline.ball.y
    );
  }, [state, baseline, lineNudge]);

  if (loading) {
    return (
      <div className="rounded border border-white/10 bg-white/5 p-8 text-center text-white/60">
        Loading scenario…
      </div>
    );
  }
  if (error || !state || !phi) {
    return (
      <div className="rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
        {error ?? "Scenario engine unavailable"}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* controls */}
      <div className="flex flex-wrap items-center gap-3 rounded border border-white/10 bg-white/5 p-3">
        <div className="text-xs uppercase tracking-[0.18em] text-white/40">
          Formation
        </div>
        {VALID_FORMATIONS.map((f) => {
          const active = formation === f;
          return (
            <button
              key={f}
              type="button"
              onClick={() => setFormation(f)}
              aria-pressed={active}
              className={`rounded px-3 py-1 text-sm font-mono transition ${
                active
                  ? "bg-accent text-ink-900"
                  : "bg-white/5 text-white/70 hover:bg-white/10 hover:text-white"
              }`}
            >
              {f}
            </button>
          );
        })}
        <div className="mx-2 h-4 w-px bg-white/10" />
        <label className="flex items-center gap-2 text-xs text-white/50">
          <span className="uppercase tracking-[0.18em]">Def line</span>
          <input
            type="range"
            min={-20}
            max={20}
            step={1}
            value={lineNudge}
            onChange={(e) => onLineNudge(Number(e.target.value))}
            className="accent-accent"
            aria-label="Shift defensive line up (negative) or back (positive) in metres"
          />
          <span className="w-16 font-mono tabular-nums text-white/80">
            {lineNudge === 0 ? "baseline" : `${lineNudge > 0 ? "+" : ""}${lineNudge} m`}
          </span>
        </label>
        <div className="mx-2 h-4 w-px bg-white/10" />
        <button
          type="button"
          onClick={onReset}
          disabled={!edited}
          className="rounded border border-white/15 px-3 py-1 text-sm text-white/70 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          Reset to baseline
        </button>
        <div className="ml-auto text-2xs font-mono tabular-nums text-white/40">
          {recomputing ? "re-computing…" : lastElapsed !== null ? `${Math.round(lastElapsed)} ms` : "ready"}
        </div>
      </div>

      {/* dynamic coach verdict — updates live as the scenario changes */}
      <ScenarioHeadline
        diff={phi.diff ?? null}
        edited={edited}
        recomputing={recomputing}
      />

      {/* pitch + live readouts */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_260px]">
        <ScenarioPitch
          attackers={state.attackers}
          defenders={state.defenders}
          ball={state.ball}
          phi={phi.phi}
          onChange={(next) =>
            applyPatch({
              attackers: next.attackers,
              defenders: next.defenders,
              ball: next.ball,
            })
          }
        />

        <aside className="flex flex-col gap-3 rounded border border-white/10 bg-white/5 p-4 text-sm">
          <div>
            <div className="text-2xs uppercase tracking-[0.2em] text-white/40">
              Defensive line height
            </div>
            <div className="font-mono text-2xl tabular-nums text-white">
              {phi.defensive_line_height_m.toFixed(1)} m
            </div>
            <div className="text-2xs text-white/40">
              from defender&apos;s own goal line
            </div>
          </div>
          {phi.zonal && (
            <>
              <div>
                <div className="text-2xs uppercase tracking-[0.2em] text-white/40">
                  Territorial balance
                </div>
                <div className="font-mono text-2xl tabular-nums text-white">
                  {phi.zonal.balance_attacker_pct.toFixed(0)}%
                </div>
                <div className="text-2xs text-white/40">
                  attacker ownership of the pitch surface
                </div>
              </div>
              <div>
                <div className="text-2xs uppercase tracking-[0.2em] text-white/40">
                  Hottest attack zone
                </div>
                <div className="text-white">
                  {phi.zonal.hottest_attack.label}
                </div>
                <div className="font-mono text-2xs tabular-nums text-white/60">
                  Φ = {phi.zonal.hottest_attack.phi_mean.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-2xs uppercase tracking-[0.2em] text-white/40">
                  Defensive weak point
                </div>
                <div className="text-white">
                  {phi.zonal.defensive_weak_point.label}
                </div>
                <div className="font-mono text-2xs tabular-nums text-white/60">
                  Φ = {phi.zonal.defensive_weak_point.phi_mean.toFixed(2)}
                </div>
              </div>
            </>
          )}
        </aside>
      </div>

      {/* four-card diff strip — baseline → current → Δ for each headline metric */}
      <ScenarioDiffCards
        diff={phi.diff ?? null}
        baseline={baselineSnapshot}
        current={currentSnapshot}
      />

      <p className="text-2xs text-white/40">
        Drag any player dot (green = attacker, magenta = defender, white = ball)
        to move them. Keyboard: tab to a dot, then arrow keys nudge 1 m (Shift
        + arrow = 5 m). Pitch is 105 × 68 m; attackers are attacking toward the
        right. Φ recomputes on a 34 × 52 grid.
      </p>

      {/* Analyst view — raw numbers + per-zone delta grid. Collapsed by
          default so coaches aren't distracted; the diff cards + headline
          above are the primary coach-facing read. */}
      <details className="group rounded border border-white/10 bg-white/5 p-3 text-xs">
        <summary className="cursor-pointer list-none select-none text-white/60 transition hover:text-white">
          <span className="mr-2 font-mono text-white/40 group-open:hidden">▸</span>
          <span className="mr-2 font-mono text-white/40 hidden group-open:inline">▾</span>
          Analyst view — per-zone Φ delta, raw line height, scenario JSON
        </summary>
        <div className="mt-3 flex flex-col gap-4">
          {phi.diff && phi.zonal ? (
            <div>
              <div className="mb-1 text-2xs uppercase tracking-[0.18em] text-white/40">
                Per-zone Φ delta (4 rows × 3 cols, final third on the right)
              </div>
              <div className="grid grid-cols-3 gap-1 font-mono tabular-nums">
                {phi.zonal.zones.map((zone, idx) => {
                  const delta = phi.diff!.per_zone_delta[idx] ?? 0;
                  const bg =
                    Math.abs(delta) < 1e-3
                      ? "bg-white/5 text-white/50"
                      : delta > 0
                        ? "bg-accent/15 text-accent"
                        : "bg-magenta/15 text-magenta-soft";
                  return (
                    <div
                      key={`${zone.channel_index}-${zone.third_index}`}
                      className={`rounded px-2 py-1 text-2xs ${bg}`}
                      title={zone.label}
                    >
                      <div className="text-white/50">{zone.label}</div>
                      <div className="font-mono">
                        {delta > 0 ? "+" : ""}
                        {delta.toFixed(3)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="text-white/50">
              Per-zone delta appears after the first edit.
            </div>
          )}

          <div>
            <div className="mb-1 text-2xs uppercase tracking-[0.18em] text-white/40">
              Raw scenario payload
            </div>
            <pre className="max-h-60 overflow-auto rounded bg-black/40 p-2 font-mono text-2xs leading-snug text-white/70">
              {JSON.stringify(
                {
                  formation,
                  baseline,
                  current: state,
                  diff: phi.diff,
                  defensive_line_height_m: phi.defensive_line_height_m,
                  zonal: phi.zonal,
                },
                null,
                2,
              )}
            </pre>
          </div>
        </div>
      </details>
    </div>
  );
}
