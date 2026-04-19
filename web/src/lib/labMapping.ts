/**
 * Shared helpers for mapping squad / recruit results into Counterfactual
 * Lab lineup slots.
 *
 * Slot order matches ``formation_preset("4-3-3", "attacker")`` on the
 * backend (``src/athletiq/metrics/scenario.py``):
 *
 *   0  GK         (10, 34)
 *   1  LB         (30, 12)
 *   2  LCB        (30, 26)
 *   3  RCB        (30, 42)
 *   4  RB         (30, 56)
 *   5  LCM        (55, 20)
 *   6  CM         (55, 34)
 *   7  RCM        (55, 48)
 *   8  LW         (82, 12)
 *   9  ST         (88, 34)
 *  10  RW         (82, 56)
 *
 * Mapping for squad ``DEFAULT_FORMATION`` (1 GK, 2 CB, 2 FB, 1 DM, 2 CM,
 * 1 AM, 1 WG, 1 ST) is deterministic; anything outside this is treated
 * best-effort. The coach is always free to drag slots around once
 * inside the Lab.
 */

import type { LabLineup } from "@/lib/labShare";

const LAB_433_FORMATION = "4-3-3" as const;

/**
 * Map an XI (positions + ids in arbitrary order) onto the 4-3-3
 * attacker preset. Unmatched slots stay ``null``.
 */
export function lineupFromXi(
  xi: readonly { position: string; player_id: string }[],
): LabLineup {
  // Queue per role so duplicates (two CBs) fall into the first free
  // slot deterministically without shuffling the caller's ordering.
  const by: Record<string, string[]> = {};
  for (const a of xi) {
    (by[a.position] ??= []).push(a.player_id);
  }

  const take = (pos: string): string | null => by[pos]?.shift() ?? null;

  // Order matters: consume in slot order so "extra" players for a given
  // position don't greedily take a slot that a later slot needs.
  const lineup: LabLineup = [
    take("GK"), //  0
    take("FB"), //  1  LB
    take("CB"), //  2  LCB
    take("CB"), //  3  RCB
    take("FB"), //  4  RB
    take("CM") ?? take("DM"), //  5  LCM
    take("DM") ?? take("CM"), //  6  CM  — prefer a natural 6
    take("CM") ?? take("AM"), //  7  RCM
    take("WG"), //  8  LW
    take("ST"), //  9  ST
    take("AM") ?? take("WG"), // 10  RW — AM drops into the wide forward if no WG left
  ];

  // Backfill any still-null slot with whatever's left so we never silently
  // drop a squad-picked player on the floor.
  const leftovers = Object.values(by).flat();
  for (let i = 0; i < lineup.length && leftovers.length > 0; i++) {
    if (lineup[i] === null) lineup[i] = leftovers.shift() ?? null;
  }

  return lineup;
}

/** Single-player slot mapping used by the ``/recruit`` CTA. */
const POSITION_TO_SLOT: Record<string, number> = {
  GK: 0,
  FB: 1,
  CB: 2,
  DM: 6,
  CM: 5,
  AM: 10,
  WG: 8,
  ST: 9,
};

/** Drop a single player into their natural 4-3-3 slot. */
export function lineupFromCandidate(
  player_id: string,
  position: string,
): LabLineup {
  const slot = POSITION_TO_SLOT[position] ?? 9;
  const lineup: LabLineup = Array.from({ length: 11 }, () => null);
  lineup[slot] = player_id;
  return lineup;
}

export { LAB_433_FORMATION };
