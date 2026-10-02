"use client";

import { isProductEvent, UUID, type EventData, type EventName, type ProductEvent } from "./analytics-contract";

const KEY = "sfr.analytics.v1";
const LIMIT = 100;
type Session = { visit: string; seq: number; queue: ProductEvent[]; started: boolean; search: string | null; query?: string; pending?: { query: string; search: string; source: EventData["source"]; previous: string | null }; profile?: { author: string; search: string; position: number; linkedAt: number }; activeProfile?: { author: string; search: string; position: number } };
let session: Session | undefined;
let initialization: Promise<Session> | undefined;
let active = false;
let timer: ReturnType<typeof setTimeout> | undefined;
let failures = 0;
let observedProfileDocument = false;
function fresh(): Session { return { visit: crypto.randomUUID(), seq: 0, queue: [], started: false, search: null }; }
function persist() {
  try { sessionStorage.setItem(KEY, JSON.stringify(session)); }
  catch { console.warn("SFR analytics: session persistence unavailable"); }
}
function page(): ProductEvent["page"] { return location.pathname.startsWith("/supervisor/") ? "profile" : location.pathname.startsWith("/results") ? "results" : "home"; }

/** sessionStorage survives reload; BroadcastChannel separates cloned/duplicated tabs. */
export async function analyticsSession(): Promise<Session> {
  if (initialization) return initialization;
  initialization = (async () => {
    try {
      const saved: unknown = JSON.parse(sessionStorage.getItem(KEY) ?? "null");
      if (saved && typeof saved === "object" && "visit" in saved && typeof saved.visit === "string" && UUID.test(saved.visit) && "seq" in saved && Number.isSafeInteger(saved.seq) && Number(saved.seq) >= 0 && "queue" in saved && Array.isArray(saved.queue) && saved.queue.length <= LIMIT && saved.queue.every(isProductEvent)) session = saved as Session;
    } catch {}
    session ??= fresh();
    if (typeof BroadcastChannel !== "undefined") {
      const channel = new BroadcastChannel("sfr.visit.v1");
      const instance = crypto.randomUUID();
      let claiming = true;
      channel.onmessage = ({ data }: MessageEvent) => {
        if (!data || data.instance === instance || data.visit !== session?.visit) return;
        if (data.kind === "probe") channel.postMessage({ kind: "owner", visit: session?.visit, instance, target: data.instance });
        if (claiming && ((data.kind === "owner" && data.target === instance) || (data.kind === "probe" && instance > data.instance))) { session = fresh(); persist(); }
      };
      channel.postMessage({ kind: "probe", visit: session.visit, instance });
      await new Promise(resolve => setTimeout(resolve, 80));
      claiming = false;
      // A hidden-but-live tab remains an owner; actual closure releases channel.
      // Browser teardown closes the channel; leave it active for BFCache restores.
    }
    persist();
    window.addEventListener("online", () => { failures = 0; void flushEvents(); });
    window.addEventListener("pagehide", () => { void flushEvents(); });
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") void flushEvents(); });
    return session;
  })();
  return initialization;
}
export function emitEvent(name: EventName, data: EventData = {}, searchId?: string | null, requestId: string | null = null): void {
  void analyticsSession().then(current => {
    if (!current.started) {
      current.started = true;
      enqueue(current, "visit_started", { viewport: window.innerWidth < 768 ? "mobile" : "desktop", release: process.env.NEXT_PUBLIC_SFR_RELEASE ?? "unknown" }, null, null);
    }
    if (name !== "visit_started") enqueue(current, name, data, searchId === undefined ? current.search : searchId, requestId);
    void flushEvents();
  });
}
function enqueue(current: Session, name: EventName, data: EventData, search: string | null, request: string | null) {
  current.seq += 1;
  if (current.queue.length >= LIMIT) {
    // Preserve oldest undelivered events; sequence gaps expose lost observations.
    console.warn("SFR analytics: delivery queue full; observation lost"); persist(); return;
  }
  current.queue.push({ schema_version: 1, event_id: crypto.randomUUID(), visit_id: current.visit, search_id: search, request_id: request, name, client_at: new Date().toISOString(), client_seq: current.seq, page: page(), data });
  persist();
}
export async function flushEvents(): Promise<void> {
  const current = await analyticsSession();
  if (active || !current.queue.length) return;
  if (timer) { clearTimeout(timer); timer = undefined; }
  active = true;
  let delivered = false;
  let deadline: ReturnType<typeof setTimeout> | undefined;
  try {
    const events = current.queue.slice(0, 10);
    while (events.length > 1 && new TextEncoder().encode(JSON.stringify({ events })).length > 16000) events.pop();
    const controller = new AbortController();
    deadline = setTimeout(() => controller.abort(), 5000);
    const response = await fetch("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ events }), keepalive: true, signal: controller.signal });
    if (response.ok) {
      const payload: unknown = await response.json();
      if (payload && typeof payload === "object" && "accepted" in payload && Array.isArray(payload.accepted)) {
        const sent = new Set(events.map(event => event.event_id));
        const accepted = new Set(payload.accepted.filter(id => typeof id === "string" && sent.has(id)));
        delivered = accepted.size > 0;
        current.queue = current.queue.filter(event => !accepted.has(event.event_id));
        persist();
      }
    }
  } catch { /* Closed tabs/offline network cannot guarantee client observations. */ }
  finally {
    if (deadline) clearTimeout(deadline);
    active = false;
    failures = delivered ? 0 : failures + 1;
    if (current.queue.length) timer = setTimeout(() => { void flushEvents(); }, delivered ? 100 : Math.min(60000, 1000 * 2 ** Math.min(failures, 6)));
  }
}
export async function prepareSearch(query: string, source: EventData["source"] = "submitted"): Promise<string> {
  const current = await analyticsSession();
  const search = crypto.randomUUID();
  current.pending = { query, search, source, previous: current.search };
  persist();
  if (source === "topic") emitEvent("topic_followed", { source, ...(current.search ? { previous_search_id: current.search } : {}) }, search);
  else if (source === "reformulated") emitEvent("search_reformulated", { source, ...(current.search ? { previous_search_id: current.search } : {}) }, search);
  return search;
}
export async function beginSearch(query: string, source?: EventData["source"]): Promise<{ visit: string; search: string; request: string }> {
  const current = await analyticsSession();
  if (source || current.pending?.query !== query) await prepareSearch(query, source ?? (current.query === query ? "repeat" : "direct"));
  const pending = current.pending!;
  current.search = pending.search; current.query = query; delete current.pending; delete current.profile; delete current.activeProfile; persist();
  const request = crypto.randomUUID();
  emitEvent("search_attempt", { source: pending.source, ...(pending.previous ? { previous_search_id: pending.previous } : {}) }, current.search, request);
  return { visit: current.visit, search: current.search, request };
}
export async function linkProfile(author: string, search: string, position: number): Promise<void> {
  const current = await analyticsSession(); current.profile = { author, search, position, linkedAt: Date.now() }; persist();
}
export async function observeProfile(author: string): Promise<void> {
  const current = await analyticsSession();
  const reload = !observedProfileDocument && typeof performance.getEntriesByType === "function" && performance.getEntriesByType("navigation").some(entry => (entry as PerformanceNavigationTiming).type === "reload");
  const context = current.profile?.author === author && Date.now() - current.profile.linkedAt >= 0 && Date.now() - current.profile.linkedAt <= 30000 ? current.profile : reload && current.activeProfile?.author === author ? current.activeProfile : null;
  observedProfileDocument = true;
  delete current.profile;
  current.activeProfile = context ?? undefined;
  current.search = context?.search ?? null; persist();
  emitEvent(context ? "profile_opened" : "profile_direct", { author_id: author, source: context ? "results" : "direct", ...(context ? { position: context.position } : {}) }, context?.search ?? null);
}
/** Call only after committed UI and a visible document, never from SSR/prefetch. */
export function whenVisible(callback: () => void): () => void {
  let frame: number | undefined;
  let fired = false;
  const show = () => {
    if (!fired && document.visibilityState !== "hidden") {
      fired = true;
      document.removeEventListener("visibilitychange", show);
      frame = requestAnimationFrame(callback);
    }
  };
  if (document.visibilityState === "hidden") document.addEventListener("visibilitychange", show);
  else show();
  return () => { document.removeEventListener("visibilitychange", show); if (frame !== undefined) cancelAnimationFrame(frame); };
}
