// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/events/route";
import { POST as match } from "@/app/api/match/route";
import { proxyHeaders } from "@/lib/proxy";
import type { ProductEvent } from "@/lib/analytics-contract";
const event: ProductEvent = { schema_version: 1, event_id: "00000000-0000-4000-8000-000000000001", visit_id: "00000000-0000-4000-8000-000000000002", search_id: null, request_id: null, name: "visit_started", client_at: "2026-10-02T00:00:00Z", client_seq: 1, page: "home", data: { viewport: "mobile" } };
function request(body: unknown, headers: Record<string, string> = {}): NextRequest { return new NextRequest("http://localhost/api/events", { method: "POST", headers, body: JSON.stringify(body) }); }
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
describe("event receiver proxy", () => {
  it("acknowledges only explicit persisted IDs, retries unchanged identifiers", async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new Error("unavailable")).mockResolvedValueOnce(Response.json({ accepted: [event.event_id] }, { status: 202 }));
    vi.stubGlobal("fetch", fetch);
    const response = await POST(request({ events: [event] }));
    expect(response.status).toBe(202); expect(await response.json()).toEqual({ accepted: [event.event_id] });
    expect(fetch).toHaveBeenCalledTimes(2); expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
  });
  it.each([{}, { accepted: [] }, { accepted: ["unknown"] }])("cannot fabricate persistence from malformed upstream ack %j", async payload => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(payload)));
    const response = await POST(request({ events: [event] }));
    expect(response.status).toBe(503);
  });
  it("refuses unknown fields, oversized batches, timezone-less clocks and text in events", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    for (const body of [{ events: Array.from({ length: 11 }, () => event) }, { events: [{ ...event, data: { query: "sensitive text" } }] }, { events: [{ ...event, client_at: "2026-10-02T00:00:00" }] }, { events: [event], token: "secret" }]) expect((await POST(request(body))).status).toBe(422);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("measures real UTF-8 bytes and rejects cross-origin posting", async () => {
    expect((await POST(request({ events: [event], text: "я".repeat(8500) }))).status).toBe(413);
    expect((await POST(request({ events: [event] }, { origin: "https://attacker.invalid" }))).status).toBe(403);
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ accepted: [event.event_id] })));
    // HTTPS public origin with private HTTP hop remains valid for same host.
    expect((await POST(request({ events: [event] }, { host: "localhost", origin: "https://localhost" }))).status).toBe(200);
  });
  it("no false successful response on persistence outage", async () => {
    const fetch = vi.fn(async () => Response.json({ detail: "offline" }, { status: 503 })); vi.stubGlobal("fetch", fetch);
    expect((await POST(request({ events: [event] }))).status).toBe(503); expect(fetch).toHaveBeenCalledTimes(2);
  });
});
describe("closed sensitive-context forwarding", () => {
  it("never forwards auth headers, secret URL parameters or untrusted client IP", () => {
    const req = request({}, { Authorization: "SECRET_AUTH", Cookie: "SECRET_COOKIE", "Set-Cookie": "SECRET_SET", "X-Revalidate-Secret": "SECRET_REVALIDATE", "X-API-Key": "SECRET_KEY", "X-Forwarded-For": "1.2.3.4", "User-Agent": "test", Referer: "https://site.invalid/results?q=PRIVATE&token=SECRET_URL#secret", "X-SFR-Visit-ID": event.visit_id });
    const forwarded = proxyHeaders(req);
    expect(forwarded.has("X-Forwarded-For")).toBe(false);
    expect(forwarded.has("X-SFR-Client-IP")).toBe(false);
    expect(forwarded.get("X-SFR-Visit-ID")).toBe(event.visit_id);
    expect(forwarded.get("X-SFR-Referer")).toBe("https://site.invalid/results");
    expect(JSON.stringify([...forwarded])).not.toMatch(/SECRET|PRIVATE/);
    vi.stubEnv("SFR_TRUST_PROXY", "1"); expect(proxyHeaders(req).get("X-Forwarded-For")).toBe("1.2.3.4");
    expect(proxyHeaders(req).get("X-SFR-Client-IP")).toBe("1.2.3.4");
  });
  it("match carries correlation and preserves original submitted text", async () => {
    const fetch = vi.fn<(url: unknown, init: RequestInit) => Promise<Response>>().mockResolvedValue(Response.json({ confidence: "none", results: [] })); vi.stubGlobal("fetch", fetch);
    const req = new NextRequest("http://localhost/api/match", { method: "POST", body: JSON.stringify({ query: "  raw text  ", k: 10 }), headers: { "X-SFR-Search-ID": event.event_id, "X-Request-ID": event.visit_id } });
    const response = await match(req);
    expect(response.headers.get("X-Request-ID")).toBe(event.visit_id);
    expect(JSON.parse(String(fetch.mock.calls[0][1].body)).query).toBe("  raw text  ");
    expect((fetch.mock.calls[0][1].headers as Headers).get("X-SFR-Search-ID")).toBe(event.event_id);
  });
});
