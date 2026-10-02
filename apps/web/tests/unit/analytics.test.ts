import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { isProductEvent } from "@/lib/analytics-contract";
beforeEach(() => { vi.resetModules(); sessionStorage.clear(); vi.useFakeTimers(); vi.stubGlobal("BroadcastChannel", undefined); });
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals(); });
const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const stored = () => JSON.parse(sessionStorage.getItem("sfr.analytics.v1")!);
describe("durable client event delivery", () => {
  it("keeps event IDs across failed delivery and reload, removes only explicit acknowledgements", async () => {
    const fetch = vi.fn<(url: unknown, init: RequestInit) => Promise<Response>>().mockResolvedValue(Response.json({ detail: "offline" }, { status: 503 })); vi.stubGlobal("fetch", fetch);
    const first = await import("@/lib/analytics");
    first.emitEvent("letter_copy_success", { author_id: "A1234" }); await settle();
    expect(stored().queue.map((e: { name: string }) => e.name)).toEqual(["visit_started", "letter_copy_success"]);
    const ids = stored().queue.map((e: { event_id: string }) => e.event_id); const visit = stored().visit;
    vi.resetModules(); const reloaded = await import("@/lib/analytics");
    expect((await reloaded.analyticsSession()).visit).toBe(visit);
    fetch.mockImplementation(async (_url: unknown, init: RequestInit) => Response.json({ accepted: JSON.parse(String(init.body)).events.map((e: { event_id: string }) => e.event_id) }));
    await reloaded.flushEvents(); expect(stored().queue).toEqual([]);
    expect(JSON.parse(String(fetch.mock.calls.at(-1)![1].body)).events.map((e: { event_id: string }) => e.event_id)).toEqual(ids);
  });
  it("a click or 200 without acknowledgement never clears durable queued events", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ ok: true })));
    const client = await import("@/lib/analytics"); client.emitEvent("address_copy_failed", { author_id: "A1234" }); await settle();
    expect(stored().queue).toHaveLength(2); expect(stored().queue.every(isProductEvent)).toBe(true);
  });
  it("reformulation and topic traversal link to a new search, not an older result", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ accepted: [] })));
    const client = await import("@/lib/analytics");
    const a = await client.beginSearch("first", "submitted"); await client.prepareSearch("second", "topic"); const b = await client.beginSearch("second"); await settle();
    expect(b.search).not.toBe(a.search);
    const events = stored().queue; const topic = events.find((e: { name: string }) => e.name === "topic_followed");
    expect(topic.search_id).toBe(b.search); expect(topic.data.previous_search_id).toBe(a.search);
    expect(events.filter((e: { name: string }) => e.name === "visit_started")).toHaveLength(1);
    expect(events.map((e: { client_seq: number }) => e.client_seq)).toEqual([1, 2, 3, 4]);
  });
  it("separates direct profile entry from displayed result attribution", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ accepted: [] })));
    const client = await import("@/lib/analytics"); const search = await client.beginSearch("query", "submitted");
    await client.linkProfile("A1234", search.search, 2); await client.observeProfile("A1234"); await client.observeProfile("A9999"); await settle();
    const events = stored().queue; expect(events.find((e: { name: string }) => e.name === "profile_opened")).toMatchObject({ search_id: search.search, data: { position: 2 } });
    expect(events.find((e: { name: string }) => e.name === "profile_direct").search_id).toBeNull();
  });
});
