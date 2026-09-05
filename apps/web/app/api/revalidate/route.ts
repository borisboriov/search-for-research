import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

// Пост-деплойная ревалидация лендинга и sitemap (REVIEW_SFR3 High №2):
// сборка образа идёт без живого API, поэтому первый снапшот деградирован —
// после `docker compose up` деплой-процедура дёргает этот роут с секретом
// (deploy/README.md). Без секрета в окружении роут выключен совсем.
export async function POST(request: NextRequest): Promise<NextResponse> {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret) {
    return NextResponse.json({ detail: "Ревалидация не настроена." }, { status: 404 });
  }
  if (request.headers.get("x-revalidate-secret") !== secret) {
    return NextResponse.json({ detail: "Неверный секрет." }, { status: 401 });
  }
  revalidatePath("/");
  revalidatePath("/sitemap.xml");
  return NextResponse.json({ revalidated: ["/", "/sitemap.xml"] });
}
