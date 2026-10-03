import { NextRequest, NextResponse } from "next/server";

import { proxyHeaders, readBody } from "@/lib/proxy";
import { apiUrl } from "@/lib/api";

// Прокси к POST /api/match бэкенда: клиент ходит на свой origin — внутренний
// адрес API не светится наружу и CORS не нужен (SPEC_SFR3 §5).

// Валидный запрос — до 500 символов + JSON-обвязка; 4 КБ хватает с запасом,
// а тело в мегабайты не должно доходить до бэкенда (REVIEW_SFR3 Medium: OOM).
const MAX_BODY_BYTES = 4096;
// Бэкенд под нагрузкой отвечает за секунды; зависший — не должен держать
// соединение бесконечно.
const UPSTREAM_TIMEOUT_MS = 15_000;

export async function POST(request: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try { body = await readBody(request, MAX_BODY_BYTES); }
  catch (error) { return NextResponse.json({ detail: "Ожидается JSON-тело запроса." }, { status: error instanceof RangeError ? 413 : 422 }); }
  const headers = proxyHeaders(request);
  const responseHeaders = { "X-Request-ID": headers.get("X-Request-ID")! };
  try {
    const upstream = await fetch(`${apiUrl()}/api/match`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const payload = await upstream.json();
    // Статус и detail бэкенда (включая 422 с человеческим текстом) — как есть.
    return NextResponse.json(payload, { status: upstream.status, headers: responseHeaders });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return NextResponse.json(
        { detail: "Сервис подбора не ответил вовремя. Попробуй ещё раз." },
        { status: 504, headers: responseHeaders },
      );
    }
    return NextResponse.json(
      { detail: "Сервис подбора сейчас недоступен." },
      { status: 502, headers: responseHeaders },
    );
  }
}
