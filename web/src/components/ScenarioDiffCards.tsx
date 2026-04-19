"use client";

import type { ScenarioDiff } from "@/lib/api";

/**
 * Four coach-facing diff cards summarising the scenario delta vs. baseline.
 *
 * Each card shows a single metric with its baseline value, the current value,
 * and the Δ (sign-aware). The card's accent tint reflects direction — green
 * when the attacker gains territory / pushes up, magenta when the defender
 * does. Neutral slate for zero-delta, which is the initial state of the lab.
 *
 * Cards are deliberately *raw* numbers — the plain-English verdict lives in
 * `<ScenarioHeadline>` above the pitch. Analyst view exposes the per-zone
 * 4×3 delta grid that's too noisy for the coach-facing summary.
 */
export type ScenarioDiffCardsProps = {
  /** Null until the coach makes their first edit. */
  diff: ScenarioDiff | null;
  /** Baseline snapshot values (so we can render "baseline → current"). */
  baseline: {
    phi_mean: number;
    phi_final_third: number;
    balance_attacker_pct: number;
    defensive_line_height_m: number;
  };
  /** Current scenario values (so we can render the right-hand side). */
  current: {
    phi_mean: number;
    phi_final_third: number;
    balance_attacker_pct: number;
    defensive_line_height_m: number;
  };
};

type Tone = "pos" | "neg" | "neutral";

function tone(delta: number, eps: number): Tone {
  if (Math.abs(delta) < eps) return "neutral";
  return delta > 0 ? "pos" : "neg";
}

const TONE_CLASSES: Record<Tone, string> = {
  pos: "border-accent/30 bg-accent/5",
  neg: "border-magenta/30 bg-magenta/5",
  neutral: "border-white/10 bg-white/5",
};

const DELTA_TEXT: Record<Tone, string> = {
  pos: "text-accent",
  neg: "text-magenta-soft",
  neutral: "text-white/50",
};

function fmtSigned(n: number, digits = 2): string {
  if (Math.abs(n) < 10 ** -digits / 2) return `±0.${"0".repeat(digits)}`;
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}`;
}

function fmtSignedInt(n: number): string {
  if (Math.round(n) === 0) return "±0";
  return `${n > 0 ? "+" : ""}${Math.round(n)}`;
}

type CardProps = {
  title: string;
  explainer: string;
  baseline: string;
  current: string;
  delta: string;
  tone: Tone;
  recomputing?: boolean;
};

function Card({ title, explainer, baseline, current, delta, tone, recomputing }: CardProps) {
  return (
    <div
      className={`flex flex-col gap-2 rounded border p-3 transition-opacity ${TONE_CLASSES[tone]} ${
        recomputing ? "opacity-60" : "opacity-100"
      }`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-2xs uppercase tracking-[0.18em] text-white/50">
          {title}
        </div>
        <div className={`font-mono text-sm tabular-nums ${DELTA_TEXT[tone]}`}>
          {delta}
        </div>
      </div>
      <div className="flex items-baseline gap-2 font-mono text-xs tabular-nums text-white/70">
        <span className="text-white/40">{baseline}</span>
        <span className="text-white/30">→</span>
        <span className="text-white">{current}</span>
      </div>
      <div className="text-2xs leading-snug text-white/40">{explainer}</div>
    </div>
  );
}

export default function ScenarioDiffCards({
  diff,
  baseline,
  current,
}: ScenarioDiffCardsProps) {
  // When no edit has been made yet we still render the 4 cards with zero
  // deltas so the layout doesn't pop in — just in a muted neutral state.
  const d = diff ?? {
    delta_phi_mean: 0,
    delta_phi_final_third: 0,
    delta_balance_attacker_pct: 0,
    delta_defensive_line_height_m: 0,
    per_zone_delta: [],
    headline: "",
  };

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card
        title="Φ mean"
        explainer="Whole-pitch attacker dominance"
        baseline={baseline.phi_mean.toFixed(3)}
        current={current.phi_mean.toFixed(3)}
        delta={fmtSigned(d.delta_phi_mean, 3)}
        tone={tone(d.delta_phi_mean, 1e-3)}
      />
      <Card
        title="Φ final third"
        explainer="Attacker dominance in the box (x ≥ 70 m)"
        baseline={baseline.phi_final_third.toFixed(3)}
        current={current.phi_final_third.toFixed(3)}
        delta={fmtSigned(d.delta_phi_final_third, 3)}
        tone={tone(d.delta_phi_final_third, 1e-3)}
      />
      <Card
        title="Balance"
        explainer="Share of the pitch the attacker controls"
        baseline={`${baseline.balance_attacker_pct.toFixed(0)}%`}
        current={`${current.balance_attacker_pct.toFixed(0)}%`}
        delta={`${fmtSignedInt(d.delta_balance_attacker_pct)}%`}
        tone={tone(d.delta_balance_attacker_pct, 0.5)}
      />
      <Card
        title="Def-line height"
        explainer="Higher = pressing further from own goal"
        baseline={`${baseline.defensive_line_height_m.toFixed(1)} m`}
        current={`${current.defensive_line_height_m.toFixed(1)} m`}
        delta={`${fmtSigned(d.delta_defensive_line_height_m, 1)} m`}
        // Higher def-line = defender pressing higher = "pos" from def POV,
        // but from attacker-colour semantics that's magenta (def gains). We
        // label it neutral-ish: the sign just tells you which way the block
        // moved; the headline provides the verdict.
        tone={
          Math.abs(d.delta_defensive_line_height_m) < 0.5
            ? "neutral"
            : d.delta_defensive_line_height_m > 0
              ? "neg"
              : "pos"
        }
      />
    </div>
  );
}
