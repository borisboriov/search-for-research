import { afterEach, describe, expect, it, vi } from "vitest";

import { getSupervisor, listAllSupervisors } from "@/lib/api";

// Семантика get() после REVIEW_SFR3 High №1: 404 — ответ («такого НР нет»),
// сеть/5xx — исключение. Иначе сбой API кэшировался ISR как 404 на час.

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getSupervisor", () => {
  it("отдаёт карточку на 200", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ author_id: "A1" })));
    await expect(getSupervisor("A1")).resolves.toEqual({ author_id: "A1" });
  });

  it("404 → null (настоящее «нет такого НР»)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "нет" }, 404)));
    await expect(getSupervisor("A999")).resolves.toBeNull();
  });

  it("5xx → исключение, а не null: страница отвечает 500, не 404", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 503)));
    await expect(getSupervisor("A1")).rejects.toThrow("503");
  });

  it("сетевая ошибка → исключение", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    await expect(getSupervisor("A1")).rejects.toThrow("fetch failed");
  });
});

describe("listAllSupervisors", () => {
  it("склеивает страницы по next_cursor", async () => {
    const pages = [
      jsonResponse({ items: [{ author_id: "A1" }], next_cursor: "A1", total: 2 }),
      jsonResponse({ items: [{ author_id: "A2" }], next_cursor: null, total: 2 }),
    ];
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(pages.shift())));
    await expect(listAllSupervisors()).resolves.toEqual([
      { author_id: "A1" },
      { author_id: "A2" },
    ]);
  });

  it("ошибка на N-й странице → исключение, а не частичный список", async () => {
    const pages = [
      jsonResponse({ items: [{ author_id: "A1" }], next_cursor: "A1", total: 2 }),
      jsonResponse({}, 500),
    ];
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(pages.shift())));
    await expect(listAllSupervisors()).rejects.toThrow("500");
  });
});
