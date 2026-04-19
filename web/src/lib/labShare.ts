/**
 * Share-link codec for the Counterfactual Lab.
 *
 * A Lab scenario is fully described by:
 *  - ``formation``: one of ``VALID_FORMATIONS``
 *  - ``attackers`` / ``defenders`` / ``ball``: metre-space positions
 *  - ``lineup``: optional per-attacker-slot player ids (11 entries, nulls
 *    allowed). Defender / ball slots intentionally stay anonymous because
 *    this is a coach-facing tool, not a match tracker.
 *
 * The encoder keeps the payload short enough to fit in a ``?s=…`` query
 * param (< 2 kB even with all 11 player ids filled) by rounding
 * coordinates to two decimals and dropping null entries from ``lineup``.
 * We deliberately avoid base64 + compression so the URL is still a plain
 * JSON string — anyone who opens it can inspect what they're about to
 * load in the Lab before clicking through.
 */

import type { Formation, Point, ScenarioBaseline } from "@/lib/api";
import { VALID_FORMATIONS } from "@/lib/api";

export const LAB_SHARE_VERSION = 1;
export const LAB_SHARE_PARAM = "s";
/** Lightweight entry-point query params used by /squad and /recruit so they
 *  don't need to fetch formation presets just to build a deep-link. */
export const LAB_FORMATION_PARAM = "formation";
export const LAB_LINEUP_PARAM = "lineup";

export type LabLineup = (string | null)[];

export type LabShareState = {
  version: number;
  formation: Formation;
  attackers: Point[];
  defenders: Point[];
  ball: Point;
  /** ``lineup[i]`` names the attacker that occupies attacker-slot ``i``. */
  lineup: LabLineup;
};

export type LabSharePayload = Omit<LabShareState, "version">;

function roundPt(p: Point): Point {
  return { x: Math.round(p.x * 100) / 100, y: Math.round(p.y * 100) / 100 };
}

function isFormation(x: unknown): x is Formation {
  return (
    typeof x === "string" && (VALID_FORMATIONS as readonly string[]).includes(x)
  );
}

function isPoint(x: unknown): x is Point {
  return (
    typeof x === "object" &&
    x !== null &&
    typeof (x as Point).x === "number" &&
    typeof (x as Point).y === "number" &&
    Number.isFinite((x as Point).x) &&
    Number.isFinite((x as Point).y)
  );
}

function isPointArray(x: unknown, n: number): x is Point[] {
  return Array.isArray(x) && x.length === n && x.every(isPoint);
}

export function encodeLabShare(state: LabSharePayload): string {
  const compact: Record<string, unknown> = {
    v: LAB_SHARE_VERSION,
    f: state.formation,
    a: state.attackers.map(roundPt),
    d: state.defenders.map(roundPt),
    b: roundPt(state.ball),
  };
  const trimmed = state.lineup.map((id) => (id && id.length > 0 ? id : null));
  if (trimmed.some((id) => id !== null)) compact.l = trimmed;
  return encodeURIComponent(JSON.stringify(compact));
}

export function decodeLabShare(raw: string): LabShareState | null {
  try {
    const obj = JSON.parse(decodeURIComponent(raw)) as {
      v?: unknown;
      f?: unknown;
      a?: unknown;
      d?: unknown;
      b?: unknown;
      l?: unknown;
    };
    if (obj.v !== LAB_SHARE_VERSION) return null;
    if (!isFormation(obj.f)) return null;
    if (!isPointArray(obj.a, 11)) return null;
    if (!isPointArray(obj.d, 11)) return null;
    if (!isPoint(obj.b)) return null;

    let lineup: LabLineup = Array(11).fill(null);
    if (obj.l !== undefined) {
      if (!Array.isArray(obj.l) || obj.l.length !== 11) return null;
      lineup = obj.l.map((id) =>
        typeof id === "string" && id.length > 0 ? id : null,
      );
    }

    return {
      version: LAB_SHARE_VERSION,
      formation: obj.f,
      attackers: obj.a,
      defenders: obj.d,
      ball: obj.b,
      lineup,
    };
  } catch {
    return null;
  }
}

export function buildLabUrl(state: LabSharePayload, origin?: string): string {
  const encoded = encodeLabShare(state);
  const base = origin ?? "";
  return `${base}/lab?${LAB_SHARE_PARAM}=${encoded}`;
}

export type LabLineupHint = {
  formation: Formation | null;
  lineup: LabLineup | null;
};

/**
 * Parse the lightweight ``?formation=…&lineup=…`` params used by /squad &
 * /recruit. Lineup is a plain JSON array of 11 strings or nulls; formation
 * must be one of the canonical four or it is dropped.
 */
export function parseLabHint(search: URLSearchParams): LabLineupHint {
  let formation: Formation | null = null;
  const rawFormation = search.get(LAB_FORMATION_PARAM);
  if (rawFormation && isFormation(rawFormation)) formation = rawFormation;

  let lineup: LabLineup | null = null;
  const rawLineup = search.get(LAB_LINEUP_PARAM);
  if (rawLineup) {
    try {
      const parsed = JSON.parse(decodeURIComponent(rawLineup));
      if (Array.isArray(parsed) && parsed.length === 11) {
        lineup = parsed.map((id) =>
          typeof id === "string" && id.length > 0 ? id : null,
        );
      }
    } catch {
      lineup = null;
    }
  }

  return { formation, lineup };
}

/** Build a lightweight /lab deep-link carrying only formation + lineup. */
export function buildLabHintUrl(
  formation: Formation,
  lineup: LabLineup,
  origin?: string,
): string {
  const trimmed = lineup.map((id) => (id && id.length > 0 ? id : null));
  const params = new URLSearchParams();
  params.set(LAB_FORMATION_PARAM, formation);
  if (trimmed.some((id) => id !== null)) {
    params.set(LAB_LINEUP_PARAM, encodeURIComponent(JSON.stringify(trimmed)));
  }
  const base = origin ?? "";
  return `${base}/lab?${params.toString()}`;
}

/** Coerce a scenario state into its ``ScenarioBaseline`` twin. */
export function lineupToBaseline(state: {
  attackers: Point[];
  defenders: Point[];
  ball: Point;
}): ScenarioBaseline {
  return {
    attackers: state.attackers,
    defenders: state.defenders,
    ball: state.ball,
  };
}
