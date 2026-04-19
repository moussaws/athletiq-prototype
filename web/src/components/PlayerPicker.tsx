"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { API_BASE, type Player } from "@/lib/api";

/**
 * Modal for swapping a real FBRef cohort player into an attacker slot.
 *
 * Fetches ``/api/players`` lazily the first time it opens and caches the
 * cohort in component state. Search filters on name / nationality;
 * position pills restrict the pool to a single role at a time.
 */
export type PlayerPickerProps = {
  open: boolean;
  /** 0-indexed attacker slot being edited, for the title. */
  slotIndex: number | null;
  /** Player currently occupying this slot, for the "unassign" affordance. */
  current?: Player | null;
  onClose: () => void;
  onSelect: (p: Player | null) => void;
};

const POSITION_ORDER = ["ST", "WG", "AM", "CM", "DM", "FB", "CB", "GK"];

export default function PlayerPicker({
  open,
  slotIndex,
  current,
  onClose,
  onSelect,
}: PlayerPickerProps) {
  const [players, setPlayers] = useState<Player[] | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [position, setPosition] = useState<string>("ALL");
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Lazy-fetch the first time the modal opens in this page session.
  // `loading` is intentionally NOT in the deps: toggling it would re-run
  // this effect and cancel its own in-flight fetch under StrictMode, leaving
  // `loading=true` pinned forever. We still read it via closure for the guard.
  useEffect(() => {
    if (!open) return;
    if (players !== null || loading) return;
    let cancelled = false;
    setLoading(true);
    setLoadErr(null);
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/api/players?limit=500`, {
          cache: "no-store",
        });
        if (!r.ok) throw new Error(`players GET ${r.status}`);
        const data = (await r.json()) as { items: Player[] };
        if (!cancelled) setPlayers(data.items);
      } catch (e) {
        if (!cancelled) {
          setLoadErr(e instanceof Error ? e.message : String(e));
        }
      } finally {
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, players]);

  // Close on Escape & click-outside.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const filtered = useMemo(() => {
    if (!players) return [];
    const q = query.trim().toLowerCase();
    return players
      .filter((p) => position === "ALL" || p.position === position)
      .filter(
        (p) =>
          q === "" ||
          p.name.toLowerCase().includes(q) ||
          p.nationality.toLowerCase().includes(q),
      )
      .slice(0, 120);
  }, [players, position, query]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Player picker"
    >
      <div
        ref={panelRef}
        className="flex h-[min(85vh,640px)] w-[min(90vw,560px)] flex-col gap-3 overflow-hidden rounded border border-white/10 bg-ink-900 p-4 text-sm shadow-2xl"
      >
        <header className="flex items-baseline justify-between gap-2">
          <div>
            <div className="text-2xs uppercase tracking-[0.2em] text-white/40">
              Swap player
            </div>
            <div className="text-white">
              Attacker slot{" "}
              <span className="font-mono tabular-nums text-accent">
                #{(slotIndex ?? 0) + 1}
              </span>
              {current ? (
                <span className="ml-2 text-white/50">
                  currently <span className="text-white">{current.name}</span>
                </span>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-white/15 px-2 py-1 text-xs text-white/70 hover:bg-white/10 hover:text-white"
          >
            Close
          </button>
        </header>

        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or nationality"
          className="w-full rounded border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/30 focus:border-accent focus:outline-none"
          autoFocus
        />

        <div className="flex flex-wrap gap-1 text-xs">
          <button
            type="button"
            onClick={() => setPosition("ALL")}
            aria-pressed={position === "ALL"}
            className={`rounded px-2 py-1 ${
              position === "ALL"
                ? "bg-accent text-ink-900"
                : "bg-white/5 text-white/60 hover:bg-white/10"
            }`}
          >
            ALL
          </button>
          {POSITION_ORDER.map((pos) => (
            <button
              key={pos}
              type="button"
              onClick={() => setPosition(pos)}
              aria-pressed={position === pos}
              className={`rounded px-2 py-1 font-mono ${
                position === pos
                  ? "bg-accent text-ink-900"
                  : "bg-white/5 text-white/60 hover:bg-white/10"
              }`}
            >
              {pos}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-auto rounded border border-white/10 bg-black/30">
          {loadErr ? (
            <div className="p-4 text-magenta-soft">{loadErr}</div>
          ) : loading ? (
            <div className="p-4 text-white/60">Loading cohort…</div>
          ) : filtered.length === 0 ? (
            <div className="p-4 text-white/50">
              No players match the current filters.
            </div>
          ) : (
            <ul className="divide-y divide-white/5">
              {filtered.map((p) => (
                <li key={p.player_id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(p);
                      onClose();
                    }}
                    className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition hover:bg-white/5"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-white">{p.name}</div>
                      <div className="text-2xs text-white/50">
                        {p.nationality} · {p.age}y · €{p.market_value_m.toFixed(1)}M
                      </div>
                    </div>
                    <span className="shrink-0 rounded bg-white/5 px-2 py-1 font-mono text-2xs uppercase tracking-widest text-white/70">
                      {p.position}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {current ? (
          <button
            type="button"
            onClick={() => {
              onSelect(null);
              onClose();
            }}
            className="self-start rounded border border-magenta/30 bg-magenta/10 px-3 py-1 text-xs text-magenta-soft hover:bg-magenta/20"
          >
            Unassign slot
          </button>
        ) : null}
      </div>
    </div>
  );
}
