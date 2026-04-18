/**
 * Coach-friendly squad philosophy presets. Each preset bakes out a hand-tuned
 * 5×5 AHP pairwise matrix that, once run through `/api/squad/ahp`, produces
 * the weight distribution described in `summary`. The raw Saaty matrix stays
 * editable under "Analyst view" so advanced users can still tune by hand.
 */

export type SquadPhilosophyKey =
  | "press_heavy"
  | "possession"
  | "direct"
  | "balanced";

export type SquadPhilosophy = {
  key: SquadPhilosophyKey;
  label: string;
  tagline: string;
  summary: string;
  criteria: string[];
  matrix: number[][];
};

export const SQUAD_PHILOSOPHIES: SquadPhilosophy[] = [
  {
    key: "press_heavy",
    label: "Press-heavy",
    tagline: "Win it back fast.",
    summary:
      "Heavy on defensive work: tackles, interceptions, DDI. Ball progression is a tie-breaker.",
    criteria: [
      "ddi",
      "interceptions",
      "tackles",
      "xt_carry",
      "passes_completed",
    ],
    matrix: [
      [1, 2, 3, 4, 5],
      [1 / 2, 1, 2, 3, 4],
      [1 / 3, 1 / 2, 1, 2, 3],
      [1 / 4, 1 / 3, 1 / 2, 1, 2],
      [1 / 5, 1 / 4, 1 / 3, 1 / 2, 1],
    ],
  },
  {
    key: "possession",
    label: "Possession",
    tagline: "Keep it, move it, break them open.",
    summary:
      "Leans on retention and progression: passes completed, PABR, carry xT.",
    criteria: [
      "passes_completed",
      "pabr",
      "xt_carry",
      "take_ons",
      "ddi",
    ],
    matrix: [
      [1, 2, 3, 5, 6],
      [1 / 2, 1, 2, 4, 5],
      [1 / 3, 1 / 2, 1, 3, 4],
      [1 / 5, 1 / 4, 1 / 3, 1, 2],
      [1 / 6, 1 / 5, 1 / 4, 1 / 2, 1],
    ],
  },
  {
    key: "direct",
    label: "Direct",
    tagline: "Straight through. Fast.",
    summary:
      "Leans on verticality and final-third output: carry xT, shots, sprints, accelerations.",
    criteria: [
      "xt_carry",
      "shots",
      "sprint_count",
      "accel_count",
      "take_ons",
    ],
    matrix: [
      [1, 2, 3, 4, 5],
      [1 / 2, 1, 2, 3, 4],
      [1 / 3, 1 / 2, 1, 2, 3],
      [1 / 4, 1 / 3, 1 / 2, 1, 2],
      [1 / 5, 1 / 4, 1 / 3, 1 / 2, 1],
    ],
  },
  {
    key: "balanced",
    label: "Balanced",
    tagline: "No dominant phase.",
    summary:
      "Equal weight across attacking, possession, defensive, and athletic criteria.",
    criteria: [
      "pabr",
      "xt_carry",
      "ddi",
      "interceptions",
      "passes_completed",
    ],
    matrix: [
      [1, 1, 1, 1, 1],
      [1, 1, 1, 1, 1],
      [1, 1, 1, 1, 1],
      [1, 1, 1, 1, 1],
      [1, 1, 1, 1, 1],
    ],
  },
];
