import { describe, expect, it } from "vitest";

import {
  affiliationLine,
  counterText,
  formatIndexDate,
  formatNumber,
  initials,
  institutionShort,
  pluralize,
  truncateTitle,
} from "@/lib/utils";

describe("initials", () => {
  it("берёт первые буквы первых двух слов", () => {
    expect(initials("Ivan Smirnov")).toBe("IS");
    expect(initials("Ковалёв Алексей Владимирович")).toBe("КА");
  });
  it("пропускает сокращения из точек и лишние пробелы", () => {
    expect(initials("Л. В. Инжечик")).toBe("ЛВ");
    expect(initials("  Boris   Zhivotovsky ")).toBe("BZ");
  });
  it("одно слово — одна буква", () => {
    expect(initials("Аристотель")).toBe("А");
  });
});

describe("formatNumber", () => {
  it("разделяет тысячи по-русски", () => {
    expect(formatNumber(2140)).toBe("2\u00A0140");
    expect(formatNumber(535)).toBe("535");
  });
});

describe("pluralize", () => {
  it.each([
    [1, "вуз"],
    [2, "вуза"],
    [5, "вузов"],
    [11, "вузов"],
    [21, "вуз"],
  ])("%i → %s", (count, expected) => {
    expect(pluralize(count, "вуз", "вуза", "вузов")).toBe(expected);
  });
});

describe("institutionShort / affiliationLine", () => {
  it("знакомые вузы сокращаются", () => {
    expect(institutionShort("Московский физико-технический институт")).toBe("МФТИ");
    expect(institutionShort("Московский государственный университет")).toBe("МГУ");
  });
  it("незнакомый вуз остаётся полным, null остаётся null", () => {
    expect(institutionShort("НГУ им. Лобачевского")).toBe("НГУ им. Лобачевского");
    expect(institutionShort(null)).toBeNull();
  });
  it("строка аффилиации собирается только из имеющихся частей", () => {
    expect(affiliationLine("Московский государственный университет", null)).toBe("МГУ");
    expect(affiliationLine("Московский государственный университет", "профессор")).toBe(
      "МГУ · профессор",
    );
    expect(affiliationLine(null, null)).toBe("");
  });
});

describe("counterText (S-09, «вуз» → «организация»)", () => {
  it("считает научруков и организации выдачи", () => {
    expect(counterText(10, 6)).toBe("Нашли 10 научруков из 6 организаций");
    expect(counterText(1, 1)).toBe("Нашли 1 научрука из 1 организации");
    expect(counterText(3, 2)).toBe("Нашли 3 научрука из 2 организаций");
    expect(counterText(0, 0)).toBe("Нашли 0 научруков из 0 организаций");
  });
  it("слова «вуз» в счётчике больше нет", () => {
    expect(counterText(12, 12)).not.toMatch(/вуз/);
  });
});

describe("truncateTitle (P-15)", () => {
  it("короткое название не трогает", () => {
    expect(truncateTitle("Depression detection")).toBe("Depression detection");
  });
  it("длинное режет по границе слова и ставит многоточие", () => {
    const long =
      "RussianSuperGLUE: A Russian Language Understanding Evaluation Benchmark for Neural Models";
    const short = truncateTitle(long);
    expect(short.endsWith("…")).toBe(true);
    expect(short.length).toBeLessThanOrEqual(65);
    expect(long.startsWith(short.slice(0, -1))).toBe(true);
    expect(short).toBe("RussianSuperGLUE: A Russian Language Understanding Evaluation…");
  });
  it("длинное слово без пробелов режется по лимиту", () => {
    const solid = "a".repeat(90);
    expect(truncateTitle(solid)).toBe(`${"a".repeat(64)}…`);
  });
});

describe("formatIndexDate (плашка P-08)", () => {
  it("ISO из /health → дата в UTC", () => {
    expect(formatIndexDate("2026-09-05T23:48:27+00:00")).toBe("05.09.2026");
  });
  it("нет даты или мусор — null, плашка остаётся без даты", () => {
    expect(formatIndexDate(null)).toBeNull();
    expect(formatIndexDate(undefined)).toBeNull();
    expect(formatIndexDate("")).toBeNull();
    expect(formatIndexDate("не дата")).toBeNull();
  });
});
