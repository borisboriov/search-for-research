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
  it("оставляет обращение для студента и не подставляет имя из OpenAlex", () => {
    const letter = buildLetter(CARD);
    expect(letter).toContain("Здравствуйте, [Имя Отчество]!");
    expect(letter).not.toContain("Ivan Smirnov");
  });
  it("без явного выбора не утверждает, что студент читал публикацию", () => {
    const letter = buildLetter(CARD);
    expect(letter).not.toContain(CARD.top_works[0]!.title);
    expect(letter).not.toContain("Прочитал");
  });
  it("включает явно переданную выбранную работу с годом", () => {
    expect(buildLetter(CARD, CARD.top_works[0])).toContain(
      "«Detecting depression in social media» (2023)",
    );
  });
  it("без работ — без пустых кавычек и утверждения о прочитанных публикациях", () => {
    const letter = buildLetter({ ...CARD, top_works: [] });
    expect(letter).not.toContain("«");
    expect(letter).not.toContain("Ваши публикации");
    expect(letter).not.toContain("Прочитал");
  });
  it("неизвестный год не попадает в письмо", () => {
    const work = { title: "Undated publication", year: null };
    const letter = buildLetter({ ...CARD, top_works: [work] }, work);
    expect(letter).toContain("«Undated publication» —");
    expect(letter).not.toContain("null");
    expect(letter).not.toContain("()");
  });
  it("не включает работу чужого профиля", () => {
    const letter = buildLetter(CARD, { title: "Other publication", year: 2025 });
    expect(letter).not.toContain("Other publication");
  });
  it("оставляет студенту поля и место для своей задачи", () => {
    const letter = buildLetter(CARD);
    expect(letter).toContain("[Имя Фамилия]");
    expect(letter).toContain("[какую задачу хочу решать / тема ВКР]");
  });
});

describe("claimProfileMailto", () => {
  it("тема письма содержит author_id (по нему находят профиль)", () => {
    const href = claimProfileMailto("A5070267730");
    expect(href.startsWith("mailto:")).toBe(true);
    expect(decodeURIComponent(href)).toContain("A5070267730");
  });
});
