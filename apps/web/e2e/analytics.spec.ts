import { writeFile } from "node:fs/promises";
import { expect, test, type Page } from "./fixtures";
import type { ProductEvent } from "../lib/analytics-contract";
import { KNOWN_AUTHOR_ID } from "./helpers";

// Synthetic matches verify browser instrumentation, not FRIDA ranking.
// Optional live receiver additionally verifies Next → API durable acknowledgements.
let captures: ProductEvent[][] = [];
test.beforeEach(() => { captures = []; });
test.afterEach(async ({ page }, info) => {
  await page.unrouteAll({ behavior: "wait" });
  const events = [...new Map(captures.flat().map(event => [event.event_id, event])).values()];
  const counts: Record<string, number> = {};
  for (const event of events) counts[event.name] = (counts[event.name] ?? 0) + 1;
  const proof = info.outputPath("analytics-acknowledged-events.json");
  await writeFile(proof, JSON.stringify({ schema_version: 1, live_receiver: process.env.SFR_ANALYTICS_LIVE_RECEIVER === "1", counts, events: events.map(({ event_id, visit_id, search_id, name, client_seq }) => ({ event_id, visit_id, search_id, name, client_seq })) }, null, 2), { mode: 0o600 });
  await info.attach("analytics-acknowledged-events", { contentType: "application/json", path: proof });
});
async function capture(page: Page): Promise<ProductEvent[]> {
  const events: ProductEvent[] = [];
  captures.push(events);
  await page.route("**/api/events", async route => {
    const batch = route.request().postDataJSON().events as ProductEvent[];
    if (process.env.SFR_ANALYTICS_LIVE_RECEIVER === "1") {
      const response = await route.fetch();
      expect(response.ok(), "real receiver must confirm durable persistence").toBe(true);
      const payload = await response.json();
      expect(payload.accepted).toEqual(expect.arrayContaining(batch.map(event => event.event_id)));
      await route.fulfill({ response, json: payload });
    } else await route.fulfill({ json: { accepted: batch.map(event => event.event_id) } });
    // Test observations are acknowledged durable facts in live mode.
    for (const event of batch) if (!events.some(previous => previous.event_id === event.event_id)) events.push(event);
  });
  return events;
}
async function matches(page: Page, confidence: "none" | "weak" | "ok" = "ok") {
  await page.route("**/api/match", route => route.fulfill({ json: { confidence, below_threshold: confidence === "none", index_version: "synthetic-test", took_ms: 1, results: confidence === "none" ? [] : [{ author_id: KNOWN_AUTHOR_ID, name: "Synthetic researcher", institution: "МФТИ", h_index: 30, works_count: 1, topics: ["Topic Modeling"], profile_text: "", cited_by_count: 1, position: null, email: null, top_works: [{ title: "Synthetic publication", year: 2025 }], serendipity: false, score: 0.55, rank: 1, grade: "high" }] } }));
}
const names = (events: ProductEvent[]) => events.map(event => event.name);

test("observed results → profile → successful/failed clipboard; SSR/prefetch produce no profile event", async ({ page }) => {
  const events = await capture(page); await matches(page);
  await page.goto("/results?q=" + encodeURIComponent("  synthetic topic  "));
  await expect(page.getByRole("heading", { name: "Synthetic researcher" })).toBeVisible();
  await expect.poll(() => names(events)).toContain("results_shown");
  expect(events.filter(event => event.name === "search_attempt")).toHaveLength(1);
  const attempt = events.find(event => event.name === "search_attempt")!;
  // This technical GET does not mount a client observer; no inferred human view.
  await page.request.get(`/supervisor/${KNOWN_AUTHOR_ID}`);
  await page.getByRole("link", { name: "Открыть профиль", exact: true }).hover();
  expect(names(events)).not.toContain("profile_opened");
  await page.getByRole("link", { name: "Открыть профиль", exact: true }).click();
  await expect.poll(() => names(events)).toContain("profile_opened");
  expect(events.find(event => event.name === "profile_opened")).toMatchObject({ search_id: attempt.search_id, data: { position: 1 } });
  await page.getByRole("combobox", { name: "Работа для письма" }).selectOption("1");
  await page.getByRole("checkbox", { name: "Добавить выбранную работу в письмо" }).check();
  await page.evaluate(() => { Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } }); });
  await page.getByRole("button", { name: "Скопировать письмо" }).click();
  await expect.poll(() => names(events)).toContain("letter_copy_success");
  await page.evaluate(() => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => { throw new Error("denied"); } } });
    document.execCommand = () => false;
  });
  await page.getByRole("button", { name: "Скопировано", exact: true }).click();
  await expect.poll(() => names(events)).toContain("letter_copy_failed");
  expect(names(events)).toEqual(expect.arrayContaining(["work_selected", "work_confirmed"]));
  expect(JSON.stringify(events)).not.toContain("synthetic topic");
  expect(JSON.stringify(events)).not.toContain("Черновик");
});

test("weak and empty display, repeat/topic attempts, validation and technical error remain distinct", async ({ page }) => {
  const events = await capture(page); await matches(page, "weak");
  await page.goto("/results?q=synthetic"); await expect.poll(() => names(events)).toContain("weak_shown");
  const first = events.find(event => event.name === "search_attempt")!;
  await page.getByRole("list", { name: "Ключевые темы" }).first().getByRole("link").first().click();
  await expect.poll(() => names(events)).toContain("topic_followed");
  await expect.poll(() => events.filter(event => event.name === "search_attempt").length).toBe(2);
  const second = events.filter(event => event.name === "search_attempt")[1];
  expect(second.search_id).not.toBe(first.search_id);
  expect(events.find(event => event.name === "topic_followed")?.search_id).toBe(second.search_id);
  // A topic equal to the current query still executes a fresh attempt.
  await page.getByRole("list", { name: "Ключевые темы" }).first().getByRole("link").first().click();
  await expect.poll(() => events.filter(event => event.name === "search_attempt").length).toBe(3);
  expect(events.filter(event => event.name === "search_attempt")[2].data.source).toBe("topic");
  await page.unroute("**/api/match"); await matches(page, "none");
  await page.goto("/results?q=empty-synthetic"); await expect.poll(() => names(events)).toContain("empty_shown");
  await page.unroute("**/api/match"); await page.route("**/api/match", route => route.fulfill({ status: 503, body: "unavailable" }));
  await page.goto("/results?q=error-synthetic"); await expect.poll(() => events.some(event => event.name === "search_error" && event.data.error === "http_503")).toBe(true);
  const emptyCount = events.filter(event => event.name === "empty_shown").length;
  await page.getByRole("button", { name: "Повторить" }).click();
  await expect.poll(() => events.filter(event => event.name === "search_attempt" && event.data.source === "repeat").length).toBeGreaterThan(0);
  expect(events.filter(event => event.name === "empty_shown")).toHaveLength(emptyCount);
  await page.goto("/results?q=ab"); await expect.poll(() => names(events)).toContain("search_validation_failed");
});

test("mobile filter dismissal is not application; direct profile is separate", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); const events = await capture(page); await matches(page);
  await page.goto("/results?q=synthetic"); await expect.poll(() => names(events)).toContain("results_shown");
  await page.getByRole("button", { name: "Фильтры", exact: true }).click();
  await page.getByRole("dialog").getByRole("combobox", { name: "h-index: любой" }).selectOption("20");
  await page.getByRole("dialog").getByRole("button", { name: "Закрыть" }).click();
  expect(names(events)).not.toContain("filters_applied");
  await page.getByRole("button", { name: "Фильтры", exact: true }).click();
  await page.getByRole("dialog").getByRole("combobox", { name: "h-index: любой" }).selectOption("20");
  await page.getByRole("dialog").getByRole("button", { name: "Применить" }).click();
  await expect.poll(() => names(events)).toContain("filters_applied");
  await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}`); await expect.poll(() => names(events)).toContain("profile_direct");
  expect(events.find(event => event.name === "profile_direct")?.search_id).toBeNull();
});

test("reload retains visit, duplicate/new tab starts a separate visit and offline events retry unchanged", async ({ page, context }) => {
  const events = await capture(page); await page.goto("/"); await expect.poll(() => names(events)).toContain("visit_started");
  const visit = events[0].visit_id;
  await page.reload(); await page.waitForLoadState("networkidle");
  expect(events.filter(event => event.name === "visit_started")).toHaveLength(1);
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem("sfr.analytics.v1")!).visit)).toBe(visit);
  // Emulate duplicate-tab cloned sessionStorage before hydration.
  const saved = await page.evaluate(() => sessionStorage.getItem("sfr.analytics.v1"));
  const duplicate = await context.newPage(); await duplicate.addInitScript(value => sessionStorage.setItem("sfr.analytics.v1", value!), saved);
  const duplicateEvents = await capture(duplicate); await duplicate.goto("/"); await expect.poll(() => names(duplicateEvents)).toContain("visit_started");
  expect(duplicateEvents[0].visit_id).not.toBe(visit); await duplicate.close();
  await page.unroute("**/api/events"); const unacknowledged: string[] = [];
  await page.route("**/api/events", async route => { unacknowledged.push(...route.request().postDataJSON().events.map((event: ProductEvent) => event.event_id)); await route.fulfill({ status: 503, body: "offline" }); });
  await matches(page); await page.goto("/results?q=offline-synthetic"); await expect.poll(() => unacknowledged.length).toBeGreaterThan(0);
  const queued = await page.evaluate(() => JSON.parse(sessionStorage.getItem("sfr.analytics.v1")!).queue.map((event: ProductEvent) => event.event_id));
  await page.reload(); await page.unroute("**/api/events"); const recovered = await capture(page);
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect.poll(() => queued.every((id: string) => recovered.some(event => event.event_id === id))).toBe(true);
});
