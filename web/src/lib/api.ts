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
};

export type PlayersListResponse = {
  total: number;
  items: Player[];
};

export type SimilarPlayer = {
  player_id: string;
  name: string;
  position: string;
  similarity: number;
  euclidean: number;
  cosine_similarity: number;
};

export type PitchControlResponse = {
  phi: number[][];
  x: number[];
  y: number[];
  mean: number;
  grid_shape: [number, number];
};

export type PressureResponse = {
  raw_individual: number[];
  raw_collective: number;
  collective: number;
  unit_individual: number[];
};

export type AhpResponse = {
  weights: number[];
  consistency_ratio: number;
  is_consistent: boolean;
  lambda_max: number;
};

export type SquadAssignment = {
  player_id: string;
  name: string;
  position: string;
  score: number;
  market_value_m: number;
  is_foreign: boolean;
};

export type SquadResponse = {
  assignments: Record<string, string>;
  lineup: SquadAssignment[];
  total_score: number;
  budget_used: number;
  foreign_count: number;
  squad_gap: { position: string; delta: number } | null;
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
