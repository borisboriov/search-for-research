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

/** «K публикаций по теме с <год>» — знаменатель строки «почему подошёл». */
export interface WorksOnTopic {
  count: number;
  since_year: number | null;
}

export interface MatchResult extends SupervisorCard {
  score: number;
  rank: number;
  grade: Grade;
  // Поля строки «совпало N из M» (P-18). Их даёт итерация ранжирования
  // (SFR-7) — сейчас API их не отдаёт, поэтому они опциональные, а
  // MatchEvidence скрыт. Фронт ничего из них не вычисляет сам: нет полей —
  // нет блока (DESIGN_SYSTEM v2 §4, docs/DECISIONS.md 12.09).
  matched_topics?: string[];
  query_topics?: string[];
  works_on_topic?: WorksOnTopic;
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
  institutions_count: number;
  score_threshold: number;
  score_weak: number;
  score_high: number;
  thresholds_match: boolean | null;
  search_backend: string;
  compose: string;
  built_at: string;
  /** #16: дата данных каталога (самая свежая запись OpenAlex), YYYY-MM-DD;
   * null/нет — индекс без штампа, для плашки берётся built_at. */
  data_updated_at?: string | null;
  cache_hits: number;
  cache_misses: number;
  cache_hit_rate: number;
}
