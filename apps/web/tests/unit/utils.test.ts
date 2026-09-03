import { describe, expect, it } from "vitest";

import {
  affiliationLine,
  formatNumber,
  initials,
  institutionShort,
  matchPercent,
  pluralize,
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

describe("matchPercent", () => {
  it("округляет косинусную близость до процента", () => {
    expect(matchPercent(0.921)).toBe("92%");
    expect(matchPercent(0.275)).toBe("28%");
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
