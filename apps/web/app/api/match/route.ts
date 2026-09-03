import { NextRequest, NextResponse } from "next/server";

import { apiUrl } from "@/lib/api";

// Прокси к POST /api/match бэкенда: клиент ходит на свой origin — внутренний
// адрес API не светится наружу и CORS не нужен (SPEC_SFR3 §5).
export async function POST(request: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Ожидается JSON-тело запроса." }, { status: 422 });
  }
  try {
    const upstream = await fetch(`${apiUrl()}/api/match`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const payload = await upstream.json();
    return NextResponse.json(payload, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { detail: "Сервис подбора сейчас недоступен." },
      { status: 502 },
    );
  }
}
