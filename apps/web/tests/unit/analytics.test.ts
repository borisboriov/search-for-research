import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { isProductEvent } from "@/lib/analytics-contract";
beforeEach(() => { vi.resetModules(); sessionStorage.clear(); vi.useFakeTimers(); vi.stubGlobal("BroadcastChannel", undefined); });
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals(); });
const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const stored = () => JSON.parse(sessionStorage.getItem("sfr.analytics.v1")!);
describe("durable client event delivery", () => {
  it("uses browser tab channels, not a Node-only BroadcastChannel", async () => {
    const nodeChannel = vi.fn();
    vi.stubGlobal("BroadcastChannel", nodeChannel);
    // Vitest aliases many window/global properties. A separate browser view
    // recreates Node-only availability without removing the global API itself.
    vi.stubGlobal("window", new Proxy(window, {
      get(target, key) {
        if (key === "BroadcastChannel") return undefined;
        const value = Reflect.get(target, key, target);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }));
    expect(globalThis.BroadcastChannel).toBe(nodeChannel);
    expect(window.BroadcastChannel).toBeUndefined();
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ accepted: [] })));
    const client = await import("@/lib/analytics");
    await client.analyticsSession();
    expect(nodeChannel).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });
  it("abandons delayed initialization safely when its browser document is destroyed", async () => {
    const close = vi.fn();
    const channel = vi.fn(class {
      onmessage = null;
      postMessage = vi.fn();
      close = close;
    });
    vi.stubGlobal("BroadcastChannel", channel);
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    const client = await import("@/lib/analytics");
    client.emitEvent("search_validation_failed", { error: "validation" });
    const pending = client.analyticsSession();
    expect(channel).toHaveBeenCalledOnce();
    vi.stubGlobal("window", undefined);
    await vi.advanceTimersByTimeAsync(80);
    await expect(pending).resolves.toMatchObject({ started: false, queue: [] });
    await settle();
    expect(close).toHaveBeenCalledOnce();
    expect(fetch).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });
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
  it("bounds acknowledgement body parsing as well as connection time", async () => {
    const fetch = vi.fn<(url: unknown, init: RequestInit) => Promise<Response>>().mockImplementation(async (_url, init) => ({ ok: true, json: () => new Promise((_resolve, reject) => init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))) }) as Response);
    vi.stubGlobal("fetch", fetch); const client = await import("@/lib/analytics");
    client.emitEvent("letter_copy_success", { author_id: "A1234" }); await settle();
    expect(stored().queue).toHaveLength(2); await vi.advanceTimersByTimeAsync(5000); await settle();
    fetch.mockImplementation(async (_url, init) => Response.json({ accepted: JSON.parse(String(init.body)).events.map((e: { event_id: string }) => e.event_id) }));
    await client.flushEvents(); expect(stored().queue).toEqual([]);
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
  it("concurrent retry attempts allocate distinct IDs without consuming another pending search", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ accepted: [] })));
    const client = await import("@/lib/analytics");
    const attempts = await Promise.all([client.beginSearch("query", "repeat"), client.beginSearch("query", "repeat")]); await settle();
    expect(attempts[0].search).not.toBe(attempts[1].search);
    expect(stored().queue.filter((e: { name: string }) => e.name === "search_attempt")).toHaveLength(2);
  });
  it("separates direct profile entry from displayed result attribution", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ accepted: [] })));
    const client = await import("@/lib/analytics"); const search = await client.beginSearch("query", "submitted");
    await client.linkProfile("A1234", search.search, 2); await client.observeProfile("A1234"); await client.observeProfile("A9999"); await client.observeProfile("A1234"); await settle();
    const events = stored().queue; expect(events.find((e: { name: string }) => e.name === "profile_opened")).toMatchObject({ search_id: search.search, data: { position: 2 } });
    expect(events.filter((e: { name: string }) => e.name === "profile_direct")).toHaveLength(2);
    expect(events.filter((e: { name: string }) => e.name === "profile_direct").every((e: { search_id: string | null }) => e.search_id === null)).toBe(true);
  });
});


describe("actual document visibility", () => {
  it("hidden documents wait, repeated visibility changes do not duplicate a view", async () => {
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    const frame = vi.fn((callback: FrameRequestCallback) => { callback(0); return 1; }); vi.stubGlobal("requestAnimationFrame", frame);
    const client = await import("@/lib/analytics"); const observed = vi.fn(); const cleanup = client.whenVisible(observed);
    expect(observed).not.toHaveBeenCalled();
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" }); document.dispatchEvent(new Event("visibilitychange")); document.dispatchEvent(new Event("visibilitychange"));
    expect(observed).toHaveBeenCalledTimes(1); cleanup();
  });
  it("abandoned profile navigation context expires rather than attributing future direct entries", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ accepted: [] })));
    const client = await import("@/lib/analytics"); const search = await client.beginSearch("query", "submitted");
    await client.linkProfile("A1234", search.search, 1); vi.setSystemTime(Date.now() + 31000); await client.observeProfile("A1234"); await settle();
    expect(stored().queue.find((e: { name: string }) => e.name === "profile_direct")).toMatchObject({ search_id: null });
  });
});
