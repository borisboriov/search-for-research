"use client";

import { validateQuery } from "@/components/search-box";
import { emitEvent } from "@/lib/analytics";
import type { EventData } from "@/lib/analytics-contract";
import type { MatchResponse } from "@/lib/types";

export type State =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "rate_limited" }
  | { kind: "invalid"; message: string }
  | { kind: "done"; response: MatchResponse };

/** Предел ожидания /match (P-24): дольше скелетон не крутится — показываем
 * состояние ошибки с кнопкой «Повторить». p50 запроса ≈130 мс, худший
 * замеренный случай — секунды, так что десять секунд отсекают только зависшее
 * соединение, а не медленный ответ. */
export const MATCH_TIMEOUT_MS = 10_000;

/** `AbortSignal.timeout` нет в Safari < 16.4 и в старых WebView. Вызов стоял
 * внутри общего `try`, поэтому на таких движках `TypeError` ловился тем же
 * `catch` и `/results` **всегда** показывала «Сервис недоступен» с вечной
 * кнопкой «Повторить» (REVIEW_SFR-6 Low). Нет функции — работаем без предела
 * ожидания: это хуже, чем с ним, но несравнимо лучше, чем страница-заглушка. */
function timeoutSignal(ms: number): AbortSignal | undefined {
  return typeof AbortSignal.timeout === "function" ? AbortSignal.timeout(ms) : undefined;
}

export async function fetchMatch(text: string, trace?: { visit: string; search: string; request: string }): Promise<State> {
  // Проверка интерфейса: ручной ?q=ab — подсказка про запрос,
  // а не поход в API и не ложное «Сервис недоступен» (REVIEW_SFR3 Medium).
  const invalid = validateQuery(text);
  if (invalid) {
    if (trace) emitEvent("search_validation_failed", { error: "validation", query_length: Math.min(Array.from(text).length, 100000) }, trace.search, trace.request);
    return { kind: "invalid", message: invalid };
  }
  try {
    const response = await fetch("/api/match", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(trace ? { "X-SFR-Visit-ID": trace.visit, "X-SFR-Search-ID": trace.search, "X-Request-ID": trace.request } : {}) },
      body: JSON.stringify({ query: text, k: 10 }),
      signal: timeoutSignal(MATCH_TIMEOUT_MS),
    });
    // 429 отдаёт прокси (лимит Caddy), до route handler Next: тело — не JSON,
    // поэтому статус проверяется до любого .json(). Это не «сервис лёг», а
    // «слишком часто» — отдельное сообщение (#23).
    if (!response.ok && trace) {
      const error = `http_${response.status}`;
      emitEvent("search_error", { error: ["http_422", "http_429", "http_502", "http_503", "http_504"].includes(error) ? error as EventData["error"] : "http_other" }, trace.search, trace.request);
    }
    if (response.status === 429) return { kind: "rate_limited" };
    if (response.status === 422) {
      const payload: unknown = await response.json().catch(() => null);
      const detail =
        payload !== null && typeof payload === "object" && "detail" in payload
          ? payload.detail
          : null;
      return {
        kind: "invalid",
        message:
          typeof detail === "string"
            ? detail
            : "Запрос не прошёл проверку — попробуй переформулировать.",
      };
    }
    if (!response.ok) return { kind: "error" };
    return { kind: "done", response: (await response.json()) as MatchResponse };
  } catch (error) {
    if (trace) emitEvent("search_error", { error: error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name) ? "timeout" : "network" }, trace.search, trace.request);
    return { kind: "error" };
  }
}

