"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  api,
  type PlaystyleCatalog,
  type PlaystyleInfo,
  type RecruitResponse,
} from "@/lib/api";
import { LAB_433_FORMATION, lineupFromCandidate } from "@/lib/labMapping";
import { buildLabHintUrl } from "@/lib/labShare";

const POSITIONS = ["GK", "CB", "FB", "DM", "CM", "AM", "WG", "ST"];

export default function RecruitPage() {
  const [catalog, setCatalog] = useState<PlaystyleInfo[]>([]);
  const [position, setPosition] = useState("DM");
  const [playstyle, setPlaystyle] = useState("press_resistant");
  const [maxAge, setMaxAge] = useState<string>("");
  const [maxValue, setMaxValue] = useState<string>("");
  const [limit, setLimit] = useState(10);
  const [result, setResult] = useState<RecruitResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const c = await api<PlaystyleCatalog>("/api/recruit/playstyles");
        setCatalog(c.playstyles);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, []);

  const onSearch = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await api<RecruitResponse>("/api/recruit/search", {
        method: "POST",
        body: JSON.stringify({
          position,
          playstyle,
          max_age: maxAge ? parseInt(maxAge, 10) : null,
          max_value_m: maxValue ? parseFloat(maxValue) : null,
          limit,
        }),
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const activePreset = catalog.find((p) => p.key === playstyle);

  return (
    <div className="max-w-5xl">
      <h1 className="font-display text-4xl font-semibold tracking-tightest text-white">Recruit — coach brief</h1>
      <p className="mt-2 max-w-3xl text-white/60">
        Describe the player you want in football language — role and style —
        and we&apos;ll rank the cohort by fit. No need to build weight
        matrices or pick features; the brief translates into the math for you.
      </p>

      <div className="mt-8 rounded-lg border border-white/10 bg-white/5 p-5">
        <div className="text-sm font-medium">Your brief</div>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs text-white/60">Role</span>
            <select
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              className="rounded border border-white/10 bg-rail px-3 py-2"
            >
              {POSITIONS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs text-white/60">Playstyle</span>
            <select
              value={playstyle}
              onChange={(e) => setPlaystyle(e.target.value)}
              className="rounded border border-white/10 bg-rail px-3 py-2"
            >
              {catalog.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs text-white/60">Max age (optional)</span>
            <input
              type="number"
              min={15}
              max={45}
              value={maxAge}
              onChange={(e) => setMaxAge(e.target.value)}
              placeholder="e.g. 28"
              className="rounded border border-white/10 bg-rail px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs text-white/60">
              Max market value, €M (optional)
            </span>
            <input
              type="number"
              min={0}
              step={0.5}
              value={maxValue}
              onChange={(e) => setMaxValue(e.target.value)}
              placeholder="e.g. 15"
              className="rounded border border-white/10 bg-rail px-3 py-2"
            />
          </label>
        </div>

        {activePreset && (
          <div className="mt-4 rounded border border-white/10 bg-black/20 p-3 text-xs text-white/60">
            <span className="font-medium text-white/80">
              {activePreset.label}.
            </span>{" "}
            {activePreset.description}
          </div>
        )}

        <div className="mt-4 flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-xs text-white/60">Show top</span>
            <input
              type="number"
              min={1}
              max={50}
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value, 10) || 10)}
              className="w-20 rounded border border-white/10 bg-rail px-2 py-1"
            />
          </label>
          <button
            type="button"
            onClick={onSearch}
            disabled={busy}
            className="rounded bg-accent/20 px-4 py-2 text-sm font-medium text-accent hover:bg-accent/30 disabled:opacity-50"
          >
            {busy ? "searching…" : "Find candidates"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-8">
          <div className="rounded border border-emerald-500/40 bg-emerald-500/10 p-4 text-sm text-emerald-100">
            <div className="font-medium">{result.headline}</div>
            <div className="mt-1 text-xs text-emerald-200/80">
              Searched {result.pool_size} {result.position}s for a{" "}
              {result.playstyle_label.toLowerCase()} brief.
            </div>
          </div>

          <h2 className="mt-6 text-sm font-medium text-white/80">
            Shortlist ({result.candidates.length})
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
            {result.candidates.map((c, i) => (
              <div
                key={c.player_id}
                className="rounded-lg border border-white/10 bg-white/5 p-4 transition hover:border-accent/50"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium">
                      {i + 1}. {c.name}
                    </div>
                    <div className="text-xs text-white/50">
                      {c.position} · {c.nationality} · age {c.age} · €
                      {c.market_value_m.toFixed(1)}M
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-semibold text-accent">
                      {(c.fit_score * 100).toFixed(0)}%
                    </div>
                    <div className="text-[10px] uppercase tracking-wide text-white/40">
                      fit
                    </div>
                  </div>
                </div>
                <div className="mt-3 text-xs text-white/70">{c.fit_summary}</div>
                <div className="mt-3 flex items-center gap-3 text-xs">
                  <Link
                    href={`/scouting/${c.player_id}`}
                    className="text-white/60 underline-offset-2 hover:text-white hover:underline"
                  >
                    Scouting profile →
                  </Link>
                  <a
                    href={buildLabHintUrl(
                      LAB_433_FORMATION,
                      lineupFromCandidate(c.player_id, c.position),
                    )}
                    className="rounded border border-accent/40 bg-accent/10 px-2 py-1 font-medium text-accent transition hover:bg-accent/20"
                    title="Drop this player into a 4-3-3 and open the Tactical Counterfactual Lab"
                  >
                    Open in Lab →
                  </a>
                </div>
              </div>
            ))}
          </div>

          <details className="mt-6 rounded border border-white/10 bg-white/5">
            <summary className="cursor-pointer list-none px-4 py-3 text-xs font-medium text-white/70 hover:text-white">
              Analyst view — criteria &amp; weights used
            </summary>
            <div className="border-t border-white/10 p-4 text-xs text-white/60">
              <div className="mb-2">
                WASPAS-ranked on:
              </div>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {result.criteria.map((c, i) => (
                  <div key={c} className="flex items-center gap-3">
                    <span className="w-32">{c}</span>
                    <div className="h-2 flex-1 rounded bg-white/10">
                      <div
                        className="h-2 rounded bg-accent"
                        style={{
                          width: `${Math.round(result.weights[i] * 100)}%`,
                        }}
                      />
                    </div>
                    <span className="w-12 text-right tabular-nums">
                      {(result.weights[i] * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
