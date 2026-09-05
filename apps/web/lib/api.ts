import "server-only";

import type { HealthResponse, SupervisorCard, SupervisorsPage } from "./types";

// Серверный адрес API (SSR, sitemap): внутренний, наружу не светится —
// клиентские запросы ходят через route handler /api/* (SPEC_SFR3 §5).
export function apiUrl(): string {
  return process.env.SFR_API_URL ?? "http://127.0.0.1:8000";
}

// Данные fetch не кэшируем (дефолт Next 16): кэш живёт на уровне страницы
// (ISR, revalidate 3600). Рендер, упавший при ревалидации, НЕ заменяет
// последнюю удачную версию страницы — поэтому «кэшируются только успешные
// ответы» (REVIEW_SFR3 High №1–2). 404 — это ответ («такого НР нет»),
// сеть/5xx — исключение: страница НР отдаёт 500 через error boundary,
// лендинг и sitemap ловят ошибку локально и деградируют.
async function get<T>(path: string): Promise<T | null> {
  const response = await fetch(`${apiUrl()}${path}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`API ${path} ответил ${response.status}`);
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse | null> {
  return get<HealthResponse>("/api/health");
}

export function getSupervisor(authorId: string): Promise<SupervisorCard | null> {
  return get<SupervisorCard>(`/api/supervisors/${encodeURIComponent(authorId)}`);
}

/** Весь каталог для sitemap: постранично по next_cursor.
 * Ошибка на любой странице — исключение: частичный список хуже отсутствия
 * (sitemap с половиной URL кэшировался бы на час — REVIEW_SFR3 High №2). */
export async function listAllSupervisors(): Promise<SupervisorsPage["items"]> {
  const items: SupervisorsPage["items"] = [];
  let cursor: string | null = null;
  do {
    const query: string = cursor ? `&cursor=${encodeURIComponent(cursor)}` : "";
    const page: SupervisorsPage | null = await get<SupervisorsPage>(
      `/api/supervisors?limit=1000${query}`,
    );
    if (page === null) throw new Error("API вернул 404 на страницу каталога");
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor !== null);
  return items;
}
