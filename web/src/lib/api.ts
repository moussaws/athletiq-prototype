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
