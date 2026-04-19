export const API_BASE =
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

export type CohortProvenance = {
  total: number;
  positions: Record<string, number>;
  provenance: {
    source?: string;
    season?: string;
    n_players?: number;
    competitions?: string[];
    min_minutes_filter?: number;
    market_value_real?: number;
    market_value_imputed?: number;
    proxy_features?: string[];
    proxy_note?: string;
    seed?: number;
  };
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

export type PitchZone = {
  channel_index: number;
  third_index: number;
  channel: string;
  third: string;
  label: string;
  x_range: [number, number];
  y_range: [number, number];
  x_center: number;
  y_center: number;
  phi_mean: number;
};

export type PitchZonalSummary = {
  zones: PitchZone[];
  channels: string[];
  thirds: string[];
  hottest_attack: PitchZone;
  defensive_weak_point: PitchZone;
  opportunity_zone: PitchZone;
  balance_attacker_pct: number;
  balance_defender_pct: number;
  headline: string;
};

export type PitchControlResponse = {
  phi: number[][];
  xs: number[];
  ys: number[];
  zonal?: PitchZonalSummary | null;
};

export type Point = { x: number; y: number };

export type ScenarioBaseline = {
  attackers: Point[];
  defenders: Point[];
  ball: Point;
};

export type ScenarioRequest = {
  attackers: Point[];
  defenders: Point[];
  ball: Point;
  grid_rows?: number;
  grid_cols?: number;
  baseline_seed?: number | null;
  baseline?: ScenarioBaseline | null;
};

export type ScenarioDiff = {
  delta_phi_mean: number;
  delta_phi_final_third: number;
  delta_balance_attacker_pct: number;
  delta_defensive_line_height_m: number;
  per_zone_delta: number[];
  headline: string;
};

export type ScenarioResponse = {
  phi: number[][];
  xs: number[];
  ys: number[];
  zonal?: PitchZonalSummary | null;
  diff?: ScenarioDiff | null;
  defensive_line_height_m: number;
};

export type FormationRole = "attacker" | "defender";

export type FormationPresetResponse = {
  formation: string;
  role: FormationRole;
  positions: Point[];
  ball: Point;
  valid_formations: string[];
};

export const VALID_FORMATIONS = ["4-4-2", "4-3-3", "3-5-2", "5-4-1"] as const;
export type Formation = (typeof VALID_FORMATIONS)[number];

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
  dynamic_homography?: boolean;
  n_frames_with_homography?: number;
  min_active_keypoints?: number | null;
  max_active_keypoints?: number | null;
};

export type HOTAResponse = {
  hota: number;
  deta: number;
  assa: number;
  mota: number;
  idf1: number;
  alpha: number;
  tp: number;
  fp: number;
  fn: number;
  id_switches: number;
  gt_boxes: number;
  pred_boxes: number;
  n_gt_tracks: number;
  n_pred_tracks: number;
  verdict: string;
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

export type TopPerformer = {
  role: string;
  player_id: string;
  name: string;
  position: string;
  metric_label: string;
  value: number;
  verdict: string;
};

export type TeamSummary = {
  team: string;
  players_count: number;
  total_passes: number;
  total_shots: number;
  total_take_ons: number;
  total_defensive_actions: number;
  total_xt_carry: number;
  summary: string;
  top_performers: TopPerformer[];
};

export type MatchNarrativeResponse = {
  match_id: number;
  home_team: string;
  away_team: string;
  score: string;
  headline: string;
  teams: TeamSummary[];
  imputed_features: string[];
};

export type DDILeaderboardRow = {
  player_id: string;
  name: string;
  position: string;
  ddi_m2: number;
  actions: number;
  avg_per_action: number;
  verdict: string;
};

export type DDILeaderboardResponse = {
  seed: number;
  n_actions: number;
  tau: number;
  total_ddi_m2: number;
  items: DDILeaderboardRow[];
  headline: string;
};

export type ArchetypeBucket = {
  cluster_id: number;
  size: number;
  members: string[];
  name: string;
  description: string;
  key_traits: string[];
};

export type ArchetypeResponse = {
  position: string;
  k: number;
  silhouette: number;
  buckets: ArchetypeBucket[];
};

export type PlayerStyleResponse = {
  player_id: string;
  position: string;
  style: string;
  archetype_name: string;
  archetype_description: string;
  archetype_key_traits: string[];
};

export type AhpPreference = {
  id: number;
  name: string;
  criteria: string[];
  pairwise_matrix: number[][];
  weights: number[];
  consistency_ratio: number;
  is_consistent: boolean;
  created_at: string;
};

export type SavedSquad = {
  id: number;
  name: string;
  preference_id: number | null;
  criteria: string[];
  weights: number[];
  formation: Record<string, number>;
  budget: number;
  foreign_max: number;
  assignments: SquadAssignment[];
  total_score: number;
  squad_gap_position: string | null;
  squad_gap_delta: number;
  budget_used: number;
  foreign_count: number;
  created_at: string;
};

export type PlaystyleInfo = {
  key: string;
  label: string;
  description: string;
  criteria: string[];
  weights: number[];
};

export type PlaystyleCatalog = {
  playstyles: PlaystyleInfo[];
};

export type RecruitCandidate = {
  player_id: string;
  name: string;
  position: string;
  nationality: string;
  age: number;
  market_value_m: number;
  is_foreign: boolean;
  fit_score: number;
  fit_summary: string;
  top_trait: string;
  top_trait_value: number;
};

export type RecruitResponse = {
  position: string;
  playstyle: string;
  playstyle_label: string;
  criteria: string[];
  weights: number[];
  candidates: RecruitCandidate[];
  pool_size: number;
  headline: string;
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
  if (r.status === 204) {
    return undefined as T;
  }
  return (await r.json()) as T;
}
