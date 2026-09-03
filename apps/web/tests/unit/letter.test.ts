import { describe, expect, it } from "vitest";

import { buildLetter, claimProfileMailto } from "@/lib/letter";
import type { SupervisorCard } from "@/lib/types";

const CARD: SupervisorCard = {
  author_id: "A123",
  name: "Ivan Smirnov",
  institution: "Московский физико-технический институт",
  h_index: 13,
  works_count: 88,
  topics: ["NLP"],
  profile_text: "Ivan Smirnov — МФТИ.",
  cited_by_count: 700,
  position: null,
  email: null,
  top_works: [{ title: "Detecting depression in social media", year: 2023 }],
  serendipity: false,
};

describe("buildLetter", () => {
  it("подставляет имя НР и его свежую работу", () => {
    const letter = buildLetter(CARD);
    expect(letter).toContain("Здравствуйте, Ivan Smirnov!");
    expect(letter).toContain("«Detecting depression in social media» (2023)");
  });
  it("без работ — общая формулировка вместо пустых кавычек", () => {
    const letter = buildLetter({ ...CARD, top_works: [] });
    expect(letter).toContain("Ваши публикации");
    expect(letter).not.toContain("«");
  });
  it("оставляет студенту поля в квадратных скобках", () => {
    expect(buildLetter(CARD)).toContain("[Имя Фамилия]");
  });
});

describe("claimProfileMailto", () => {
  it("тема письма содержит author_id (по нему находят профиль)", () => {
    const href = claimProfileMailto("A5070267730");
    expect(href.startsWith("mailto:")).toBe(true);
    expect(decodeURIComponent(href)).toContain("A5070267730");
  });
});
