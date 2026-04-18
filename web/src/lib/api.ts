const API_BASE =
  typeof window === "undefined"
    ? process.env.ATHLETIQ_API_URL ?? "http://localhost:8000"
    : "/backend";

export type Player = {
  player_id: string;
  name: string;
  position: string;
  nationality: string;
  age: number;
  market_value_m: number;
  is_foreign: boolean;
  features?: Record<string, number>;
};

export type PlayersListResponse = {
  total: number;
  items: Player[];
};

export type SimilarPlayer = {
  player_id: string;
  name: string;
  position: string;
  nationality: string;
  age: number;
  market_value_m: number;
  similarity: number;
  euclidean: number;
  cosine_similarity: number;
};

export type SimilarityResponse = {
  query_player_id: string;
  lam: number;
  results: SimilarPlayer[];
};

export type PitchControlResponse = {
  phi: number[][];
  xs: number[];
  ys: number[];
};

export type PressureResponse = {
  raw_individual: number[];
  raw_collective: number;
  collective: number;
  unit_individual: number[];
};

export type AhpResponse = {
  criteria: string[];
  weights: number[];
  consistency_ratio: number;
  is_consistent: boolean;
};

export type SquadAssignment = {
  position: string;
  player_id: string;
  name: string;
  nationality: string;
  age: number;
  market_value_m: number;
  is_foreign: boolean;
  positional_fit: number;
};

export type SquadResponse = {
  assignments: SquadAssignment[];
  total_score: number;
  squad_gap_position: string | null;
  squad_gap_delta: number;
  budget_used: number;
  foreign_count: number;
};

export type CVCapabilities = {
  cv_available: boolean;
  reason: string | null;
};

export type CVDetection = {
  frame: number;
  track_id: number;
  cls: number;
  conf: number;
  bbox_xyxy: [number, number, number, number] | number[];
  foot_xy: [number, number] | number[];
  pitch_xy: [number, number] | number[] | null;
};

export type CVAnalysisResponse = {
  fps: number;
  width: number;
  height: number;
  n_detections: number;
  detections: CVDetection[];
};

export type StatsBombCapabilities = {
  statsbomb_available: boolean;
  reason: string | null;
};

export type StatsBombCompetition = {
  competition_id: number;
  season_id: number;
  country_name: string;
  competition_name: string;
  season_name: string;
  competition_gender: string;
};

export type StatsBombCompetitionsResponse = {
  items: StatsBombCompetition[];
  total: number;
};

export type StatsBombMatch = {
  match_id: number;
  competition_id: number;
  season_id: number;
  match_date: string;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
};

export type StatsBombMatchesResponse = {
  items: StatsBombMatch[];
  total: number;
};

export type StatsBombMatchPlayer = {
  player_id: string;
  name: string;
  position: string;
  team: string;
  age: number;
  market_value_m: number;
  passes_completed: number;
  take_ons: number;
  shots: number;
  tackles: number;
  interceptions: number;
  xt_carry: number;
};

export type StatsBombMatchCohortResponse = {
  match_id: number;
  home_team: string;
  away_team: string;
  score: string;
  players: StatsBombMatchPlayer[];
  imputed_features: string[];
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!r.ok) {
    const text = await r.text().catch(() => r.statusText);
    throw new Error(`API ${path} failed: ${r.status} ${text}`);
  }
  return (await r.json()) as T;
}
