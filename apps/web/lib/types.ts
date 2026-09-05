// Контракт API (apps/api/src/sfr_api/schemas.py). Поля 1:1 с бэкендом.

export interface TopWork {
  title: string;
  year: number | null;
}

export interface SupervisorCard {
  author_id: string;
  name: string;
  institution: string | null;
  h_index: number | null;
  works_count: number | null;
  topics: string[];
  profile_text: string;
  cited_by_count: number | null;
  position: string | null;
  email: string | null;
  top_works: TopWork[];
  serendipity: boolean;
}

/** Словесный грейд бейджа: границы шкалы живут в настройках API (см. /health). */
export type Grade = "high" | "medium" | "low";

/** Уверенность выдачи по top-1: none — «уверенных совпадений нет»,
 * weak — серая зона (баннер, выдача остаётся), ok — обычная выдача. */
export type Confidence = "none" | "weak" | "ok";

export interface MatchResult extends SupervisorCard {
  score: number;
  rank: number;
  grade: Grade;
}

export interface MatchResponse {
  results: MatchResult[];
  below_threshold: boolean;
  confidence: Confidence;
  index_version: string;
  took_ms: number;
}

export interface SupervisorSummary {
  author_id: string;
  name: string;
  institution: string | null;
}

export interface SupervisorsPage {
  items: SupervisorSummary[];
  next_cursor: string | null;
  total: number;
}

export interface HealthResponse {
  status: string;
  model: string;
  index_version: string;
  profiles_count: number;
  score_threshold: number;
  score_weak: number;
  score_high: number;
  search_backend: string;
  compose: string;
  built_at: string;
  cache_hits: number;
  cache_misses: number;
  cache_hit_rate: number;
}
