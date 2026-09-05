import { NextRequest, NextResponse } from "next/server";

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
  // content-length — быстрый отказ; фактическая длина — защита от chunked-тел без заголовка.
  const declared = Number(request.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) {
    return NextResponse.json({ detail: "Слишком большой запрос." }, { status: 413 });
  }
  let body: unknown;
  try {
    const raw = await request.text();
    if (raw.length > MAX_BODY_BYTES) {
      return NextResponse.json({ detail: "Слишком большой запрос." }, { status: 413 });
    }
    body = JSON.parse(raw);
  } catch {
    return NextResponse.json({ detail: "Ожидается JSON-тело запроса." }, { status: 422 });
  }
  try {
    const upstream = await fetch(`${apiUrl()}/api/match`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // IP клиента для логов /match (хешируется на стороне API, не хранится
        // открытым): за прокси Next сам его не подставляет.
        "X-Forwarded-For": request.headers.get("x-forwarded-for") ?? "",
      },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const payload = await upstream.json();
    // Статус и detail бэкенда (включая 422 с человеческим текстом) — как есть.
    return NextResponse.json(payload, { status: upstream.status });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return NextResponse.json(
        { detail: "Сервис подбора не ответил вовремя. Попробуй ещё раз." },
        { status: 504 },
      );
    }
    return NextResponse.json(
      { detail: "Сервис подбора сейчас недоступен." },
      { status: 502 },
    );
  }
}
