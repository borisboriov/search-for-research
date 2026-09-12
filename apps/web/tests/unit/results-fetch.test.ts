import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchMatch } from "@/app/results/page";

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
