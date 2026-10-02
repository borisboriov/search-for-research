import { NextRequest, NextResponse } from "next/server";
import { apiUrl } from "@/lib/api";
import { isProductEvent } from "@/lib/analytics-contract";
import { proxyHeaders, readBody } from "@/lib/proxy";

export async function POST(request: NextRequest): Promise<NextResponse> {
  // Same-origin browser delivery; cross-origin POSTs are refused even if JSON.
  const origin = request.headers.get("origin");
  if (origin) {
    try { if (new URL(origin).host !== request.headers.get("host") && origin !== request.nextUrl.origin) return NextResponse.json({ detail: "Origin rejected" }, { status: 403 }); }
    catch { return NextResponse.json({ detail: "Origin rejected" }, { status: 403 }); }
  }
  let body: unknown;
  try { body = await readBody(request, 16384); }
  catch (error) { return NextResponse.json({ detail: "Invalid event body" }, { status: error instanceof RangeError ? 413 : 422 }); }
  if (body === null || typeof body !== "object" || Object.keys(body).join() !== "events" || !("events" in body) || !Array.isArray(body.events) || body.events.length < 1 || body.events.length > 10 || !body.events.every(isProductEvent)) return NextResponse.json({ detail: "Invalid events" }, { status: 422 });
  const events = body.events;
  const headers = proxyHeaders(request);
  // One bounded retry with unchanged IDs; only DB/buffer acknowledgement is success.
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const upstream = await fetch(`${apiUrl()}/api/events`, { method: "POST", headers, body: JSON.stringify(body), cache: "no-store", signal: AbortSignal.timeout(2000) });
      if (upstream.ok) {
        const payload: unknown = await upstream.json();
        const accepted = payload !== null && typeof payload === "object" && "accepted" in payload ? payload.accepted : null;
        if (Array.isArray(accepted) && accepted.every(id => typeof id === "string" && events.some(e => e.event_id === id))) return NextResponse.json({ accepted }, { status: upstream.status });
      } else if (upstream.status < 500) return NextResponse.json({ detail: "Event receiver rejected delivery" }, { status: upstream.status });
    } catch { /* No exception payload: it can include sensitive headers or URLs. */ }
  }
  return NextResponse.json({ detail: "Events could not be saved" }, { status: 503 });
}
