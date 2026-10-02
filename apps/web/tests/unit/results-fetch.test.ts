import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { emitEvent } from "@/lib/analytics";
import { fetchMatch } from "@/lib/match";

vi.mock("@/lib/analytics", () => ({ emitEvent: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const OK_RESPONSE = {
  ok: true,
  status: 200,
  json: async () => ({ results: [], confidence: "none", index_version: "test" }),
};

const QUERY = "методы машинного обучения в анализе медицинских изображений";

describe("fetchMatch: предел ожидания", () => {
  const nativeTimeout = AbortSignal.timeout;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn(async () => OK_RESPONSE);
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    // Глобал восстанавливаем всегда: иначе удалённый timeout утечёт в соседние файлы
    Object.defineProperty(AbortSignal, "timeout", {
      value: nativeTimeout,
      configurable: true,
      writable: true,
    });
    vi.unstubAllGlobals();
  });

  it("там, где AbortSignal.timeout есть, сигнал передаётся", async () => {
    const state = await fetchMatch(QUERY);
    expect(state.kind).toBe("done");
    const init = fetchSpy.mock.calls[0]?.[1] as RequestInit;
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  // REVIEW_SFR-6 Low: на Safari < 16.4 вызов бросал TypeError внутри общего try,
  // и страница всегда показывала «Сервис недоступен» вместо работы без таймаута.
  it("там, где его нет, запрос уходит без сигнала, а не падает в ошибку", async () => {
    Object.defineProperty(AbortSignal, "timeout", {
      value: undefined,
      configurable: true,
      writable: true,
    });
    const state = await fetchMatch(QUERY);
    expect(state.kind).toBe("done");
    const init = fetchSpy.mock.calls[0]?.[1] as RequestInit;
    expect(init.signal).toBeUndefined();
  });
});

describe("fetchMatch: 429 от лимитера (#23)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("429 — отдельное состояние, а не «Сервис недоступен»; тело не разбирается", async () => {
    // Caddy отвечает на лимит до route handler Next: тело пустое, не JSON.
    const json = vi.fn(async () => {
      throw new SyntaxError("Unexpected end of JSON input");
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 429, json })),
    );
    const state = await fetchMatch(QUERY);
    expect(state.kind).toBe("rate_limited");
    expect(json).not.toHaveBeenCalled();
  });

  it("прочие не-2xx по-прежнему — ошибка сервиса", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 502, json: async () => ({}) })));
    const state = await fetchMatch(QUERY);
    expect(state.kind).toBe("error");
  });
});


describe("fetchMatch explicit client error classification", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.mocked(emitEvent).mockClear(); });
  const trace = { visit: "00000000-0000-4000-8000-000000000001", search: "00000000-0000-4000-8000-000000000002", request: "00000000-0000-4000-8000-000000000003" };
  it.each([422, 429, 502, 503, 504, 500])("HTTP %i never becomes confidence none or a network error", async status => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status, json: async () => ({ detail: "rejected" }) })));
    const result = await fetchMatch(QUERY, trace); expect(result.kind).not.toBe("done");
    expect(emitEvent).toHaveBeenCalledWith("search_error", { error: status === 500 ? "http_other" : `http_${status}` }, trace.search, trace.request);
  });
  it.each([[new DOMException("timeout", "TimeoutError"), "timeout"], [new TypeError("failed"), "network"]])("transport failure is explicit %s", async (error, classification) => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw error; })); expect((await fetchMatch(QUERY, trace)).kind).toBe("error");
    expect(emitEvent).toHaveBeenCalledWith("search_error", { error: classification }, trace.search, trace.request);
  });
});
