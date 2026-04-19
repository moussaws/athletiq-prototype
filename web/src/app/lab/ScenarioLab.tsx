"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import PlayerPicker from "@/components/PlayerPicker";
import ScenarioDiffCards from "@/components/ScenarioDiffCards";
import ScenarioHeadline from "@/components/ScenarioHeadline";
import ScenarioPitch from "@/components/ScenarioPitch";
import {
  API_BASE,
  VALID_FORMATIONS,
  type Formation,
  type FormationPresetResponse,
  type Player,
  type Point,
  type ScenarioResponse,
} from "@/lib/api";
import {
  buildLabUrl,
  decodeLabShare,
  LAB_SHARE_PARAM,
  parseLabHint,
  type LabLineup,
} from "@/lib/labShare";

type ScenarioState = {
  attackers: Point[];
  defenders: Point[];
  ball: Point;
};

const EMPTY_LINEUP: LabLineup = Array.from({ length: 11 }, () => null);

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
  // Hydrate formation & lineup from the ``?s=…`` share link on first render
  // so deep-links from /squad & /recruit land in the exact scenario they
  // encoded instead of flashing through the 4-3-3 default.
  const initialShare = useMemo(() => {
    if (typeof window === "undefined") return null;
    const raw = new URLSearchParams(window.location.search).get(
      LAB_SHARE_PARAM,
    );
    if (!raw) return null;
    return decodeLabShare(raw);
  }, []);

  // Lightweight hint params from /squad and /recruit — just formation
  // + lineup, no coordinates. The Lab seeds coordinates from the
  // formation preset and overlays the lineup on top.
  const initialHint = useMemo(() => {
    if (typeof window === "undefined") return { formation: null, lineup: null };
    if (initialShare) return { formation: null, lineup: null };
    return parseLabHint(new URLSearchParams(window.location.search));
  }, [initialShare]);

  const [formation, setFormation] = useState<Formation>(
    initialShare?.formation ?? initialHint.formation ?? "4-3-3",
  );
  const [baseline, setBaseline] = useState<ScenarioState | null>(null);
  const [state, setState] = useState<ScenarioState | null>(null);
  const [lineup, setLineup] = useState<LabLineup>(
    initialShare?.lineup ?? initialHint.lineup ?? EMPTY_LINEUP,
  );
  const [lineupPlayers, setLineupPlayers] = useState<
    Record<string, Player>
  >({});
  const [pickerSlot, setPickerSlot] = useState<number | null>(null);
  const [copyFlash, setCopyFlash] = useState<"idle" | "copied">("idle");
  const didHydrateFromShare = useRef(false);
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
        // Share-link state takes precedence on first load so a ``?s=…``
        // deep-link lands on the exact coordinates encoded by the sender.
        // Subsequent formation changes fall through to the preset.
        const usingShare =
          !didHydrateFromShare.current &&
          initialShare !== null &&
          initialShare.formation === formation;
        const init: ScenarioState = usingShare
          ? {
              attackers: initialShare!.attackers,
              defenders: initialShare!.defenders,
              ball: initialShare!.ball,
            }
          : {
              attackers: atk.positions,
              defenders: dfn.positions,
              ball: atk.ball,
            };
        // Baseline is always the formation preset so the coach's diff
        // always reads "since this formation loaded" — even when the link
        // arrives pre-edited. That's a useful read on a shared scenario.
        const preset: ScenarioState = {
          attackers: atk.positions,
          defenders: dfn.positions,
          ball: atk.ball,
        };
        const baselineResp = await postScenario(preset, null);
        if (cancelled) return;
        const resp = usingShare
          ? await postScenario(init, preset)
          : baselineResp;
        if (cancelled) return;
        setBaseline(preset);
        setState(init);
        setPhi(resp);
        setBaselinePhi(baselineResp);
        setLineNudge(0);
        if (usingShare) didHydrateFromShare.current = true;
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
    // `initialShare` is memoised once on mount so it is stable across renders,
    // but eslint-plugin-react-hooks requires it in the dep array regardless.
  }, [formation, initialShare]);

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

  // Fetch Player metadata for every non-null lineup id we haven't yet
  // resolved so the Lineup panel can show real names, not just ids.
  useEffect(() => {
    const missing = lineup.filter(
      (id): id is string => !!id && !(id in lineupPlayers),
    );
    if (missing.length === 0) return;
    let cancelled = false;
    (async () => {
      const updates: Record<string, Player> = {};
      for (const id of missing) {
        try {
          const r = await fetch(
            `${API_BASE}/api/players/${encodeURIComponent(id)}`,
            { cache: "no-store" },
          );
          if (!r.ok) continue;
          const data = (await r.json()) as Player;
          updates[id] = data;
        } catch {
          // ignore — the slot just falls back to showing the id
        }
      }
      if (!cancelled && Object.keys(updates).length > 0) {
        setLineupPlayers((prev) => ({ ...prev, ...updates }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lineup, lineupPlayers]);

  // Sync the current scenario into the URL without reloading so the coach
  // can grab the address bar at any moment and share what's on screen.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!state) return;
    const url = buildLabUrl({
      formation,
      attackers: state.attackers,
      defenders: state.defenders,
      ball: state.ball,
      lineup,
    });
    const current = window.location.pathname + window.location.search;
    if (current !== url) {
      window.history.replaceState(null, "", url);
    }
  }, [formation, state, lineup]);

  const onPick = (p: Player | null) => {
    if (pickerSlot === null) return;
    const slot = pickerSlot;
    setLineup((prev) => {
      const next = [...prev];
      next[slot] = p?.player_id ?? null;
      return next;
    });
    if (p) setLineupPlayers((prev) => ({ ...prev, [p.player_id]: p }));
  };

  const resetLineup = () => setLineup(EMPTY_LINEUP);

  const shareUrl = useMemo(() => {
    if (!state || typeof window === "undefined") return "";
    return buildLabUrl(
      {
        formation,
        attackers: state.attackers,
        defenders: state.defenders,
        ball: state.ball,
        lineup,
      },
      window.location.origin,
    );
  }, [formation, state, lineup]);

  const onCopyShare = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopyFlash("copied");
      window.setTimeout(() => setCopyFlash("idle"), 1500);
    } catch {
      // Fall back silently — the URL is already in the address bar.
    }
  };

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
      xg_for: phi?.xg?.xg_for ?? 0,
      xg_against: phi?.xg?.xg_against ?? 0,
      xg_net: phi?.xg?.xg_net ?? 0,
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
        <button
          type="button"
          onClick={onCopyShare}
          className="rounded border border-accent/40 bg-accent/10 px-3 py-1 text-sm text-accent transition hover:bg-accent/20"
          title="Copy a link to the current scenario (baseline + edits + lineup)"
        >
          {copyFlash === "copied" ? "Link copied ✓" : "Copy share link"}
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

      {/* Lineup: swap any of the 11 attacker slots for a real FBRef player.
          Kept in its own section below the pitch so the pitch itself stays
          uncluttered; the picker is a separate modal. */}
      <section className="flex flex-col gap-3 rounded border border-white/10 bg-white/5 p-4">
        <header className="flex items-baseline justify-between gap-3">
          <div>
            <div className="text-2xs uppercase tracking-[0.2em] text-white/40">
              Attacker lineup
            </div>
            <div className="text-sm text-white/70">
              Swap any slot for a real FBRef Big-5 2023-24 player. Lineup
              travels in the share link; Φ math is unaffected.
            </div>
          </div>
          <button
            type="button"
            onClick={resetLineup}
            disabled={lineup.every((id) => id === null)}
            className="rounded border border-white/15 px-3 py-1 text-xs text-white/70 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            Clear lineup
          </button>
        </header>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
          {state.attackers.map((pos, idx) => {
            const id = lineup[idx];
            const p = id ? lineupPlayers[id] ?? null : null;
            const label = p?.name ?? (id ? id : "Empty");
            return (
              <button
                key={idx}
                type="button"
                onClick={() => setPickerSlot(idx)}
                className="flex flex-col items-start gap-1 rounded border border-white/10 bg-black/20 px-3 py-2 text-left text-xs transition hover:border-accent/40 hover:bg-accent/5"
                aria-label={`Edit attacker slot ${idx + 1}${p ? `, currently ${p.name}` : ""}`}
              >
                <div className="flex w-full items-baseline justify-between gap-2">
                  <span className="font-mono text-2xs tabular-nums text-white/40">
                    #{idx + 1}
                  </span>
                  {p ? (
                    <span className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-white/60">
                      {p.position}
                    </span>
                  ) : null}
                </div>
                <div
                  className={`truncate font-medium ${
                    p ? "text-white" : "text-white/40"
                  }`}
                >
                  {label}
                </div>
                <div className="text-2xs text-white/40">
                  {p
                    ? `${p.nationality} · ${p.age}y · €${p.market_value_m.toFixed(
                        1,
                      )}M`
                    : `x=${pos.x.toFixed(0)} m · y=${pos.y.toFixed(0)} m`}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* four-card diff strip — baseline → current → Δ for each headline metric */}
      <ScenarioDiffCards
        diff={phi.diff ?? null}
        baseline={baselineSnapshot}
        current={currentSnapshot}
      />

      <PlayerPicker
        open={pickerSlot !== null}
        slotIndex={pickerSlot}
        current={
          pickerSlot !== null && lineup[pickerSlot]
            ? lineupPlayers[lineup[pickerSlot]!] ?? null
            : null
        }
        onClose={() => setPickerSlot(null)}
        onSelect={onPick}
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
