/** Versioned, closed product-event contract. Never includes query or draft text. */
export const EVENT_NAMES = ["visit_started", "search_attempt", "search_validation_failed", "results_shown", "weak_shown", "empty_shown", "search_error", "profile_opened", "profile_direct", "search_reformulated", "topic_followed", "filters_applied", "sort_applied", "work_selected", "work_confirmed", "letter_copy_success", "letter_copy_failed", "address_copy_success", "address_copy_failed"] as const;
export type EventName = typeof EVENT_NAMES[number];
export type EventData = {
  author_id?: string; position?: number; work_id?: string; work_position?: number;
  previous_search_id?: string; source?: "submitted" | "repeat" | "reformulated" | "topic" | "direct" | "results";
  confidence?: "none" | "weak" | "ok";
  error?: "validation" | "http_422" | "http_429" | "http_502" | "http_503" | "http_504" | "timeout" | "network" | "receiver";
  filter_count?: number; filters?: { institution: string[]; min_h_index: number };
  sort?: "relevance" | "h_index" | "citations"; viewport?: "mobile" | "desktop";
  elapsed_ms?: number; release?: string; included?: boolean; query_length?: number;
};
export type ProductEvent = {
  schema_version: 1; event_id: string; visit_id: string; search_id: string | null;
  request_id: string | null; name: EventName; client_at: string; client_seq: number;
  page: "home" | "results" | "profile"; data: EventData;
};
export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const keys = (v: Record<string, unknown>, allowed: string[]) => Object.keys(v).every(k => allowed.includes(k));
const enumeration = (v: unknown, allowed: string[]) => typeof v === "string" && allowed.includes(v);
const number = (v: unknown, min: number, max: number) => typeof v === "number" && Number.isFinite(v) && v >= min && v <= max;
export function isProductEvent(value: unknown): value is ProductEvent {
  if (!object(value) || !keys(value, ["schema_version", "event_id", "visit_id", "search_id", "request_id", "name", "client_at", "client_seq", "page", "data"])) return false;
  if (value.schema_version !== 1 || !UUID.test(String(value.event_id)) || !UUID.test(String(value.visit_id))) return false;
  if (![value.search_id, value.request_id].every(v => v === null || (typeof v === "string" && UUID.test(v)))) return false;
  if (!enumeration(value.name, [...EVENT_NAMES]) || !enumeration(value.page, ["home", "results", "profile"]) || !Number.isSafeInteger(value.client_seq) || !number(value.client_seq, 0, Number.MAX_SAFE_INTEGER)) return false;
  if (typeof value.client_at !== "string" || value.client_at.length > 40 || !/(Z|[+-]\d\d:\d\d)$/.test(value.client_at) || !Number.isFinite(Date.parse(value.client_at))) return false;
  if (!object(value.data)) return false;
  const rules: Record<string, (v: unknown) => boolean> = {
    author_id: v => typeof v === "string" && v.length <= 100,
    work_id: v => typeof v === "string" && v.length <= 100,
    release: v => typeof v === "string" && v.length <= 100,
    position: v => Number.isInteger(v) && number(v, 1, 1000),
    work_position: v => Number.isInteger(v) && number(v, 0, 100),
    previous_search_id: v => typeof v === "string" && UUID.test(v),
    source: v => enumeration(v, ["submitted", "repeat", "reformulated", "topic", "direct", "results"]),
    confidence: v => enumeration(v, ["none", "weak", "ok"]),
    error: v => enumeration(v, ["validation", "http_422", "http_429", "http_502", "http_503", "http_504", "timeout", "network", "receiver"]),
    filter_count: v => Number.isInteger(v) && number(v, 0, 100),
    filters: v => object(v) && keys(v, ["institution", "min_h_index"]) && Array.isArray(v.institution) && v.institution.length <= 20 && v.institution.every(x => typeof x === "string" && x.length <= 200) && number(v.min_h_index, 0, 10000),
    sort: v => enumeration(v, ["relevance", "h_index", "citations"]),
    viewport: v => enumeration(v, ["mobile", "desktop"]), elapsed_ms: v => number(v, 0, 86400000), included: v => typeof v === "boolean", query_length: v => Number.isInteger(v) && number(v, 0, 100000),
  };
  return Object.entries(value.data).every(([k, v]) => rules[k]?.(v) === true);
}
