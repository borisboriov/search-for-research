import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MatchEvidence } from "@/components/match-evidence";
import { SupervisorResultCard } from "@/components/supervisor-card";
import type { MatchResult } from "@/lib/types";

// Строка «почему подошёл» (P-18) рендерится только тогда, когда /match отдал
// matched_topics / query_topics / works_on_topic. Этих полей ещё нет — их даёт
// итерация ранжирования (SFR-7), поэтому «показан» проверяется на синтетическом
// ответе, а «скрыт» — на настоящей форме ответа API.

const BASE: MatchResult = {
  author_id: "A1",
  name: "Ivan Smirnov",
  institution: "Московский физико-технический институт",
  h_index: 13,
  works_count: 88,
  topics: ["NLP"],
  profile_text: "Ivan Smirnov — МФТИ.",
  cited_by_count: 700,
  position: null,
  email: null,
  top_works: [{ title: "Depression detection", year: 2023 }],
  serendipity: false,
  score: 0.4321,
  rank: 1,
  grade: "high",
};

const WITH_EVIDENCE: MatchResult = {
  ...BASE,
  matched_topics: ["NLP", "Topic Modeling", "Speech"],
  query_topics: ["NLP", "Topic Modeling", "Speech", "Dialogue"],
  works_on_topic: { count: 14, since_year: 2021 },
};

describe("MatchEvidence: полей нет — блока нет", () => {
  it("на сегодняшнем ответе /match (без трёх полей) не рендерится", () => {
    const { container } = render(<MatchEvidence result={BASE} />);
    expect(container).toBeEmptyDOMElement();
  });

  it.each([
    ["matched_topics", { ...WITH_EVIDENCE, matched_topics: undefined }],
    ["query_topics", { ...WITH_EVIDENCE, query_topics: undefined }],
    ["works_on_topic", { ...WITH_EVIDENCE, works_on_topic: undefined }],
  ])("нет одного поля (%s) — блока нет целиком", (_name, result) => {
    const { container } = render(<MatchEvidence result={result as MatchResult} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("в карточке результата блок тоже отсутствует", () => {
    render(<SupervisorResultCard result={BASE} query="nlp" />);
    expect(screen.queryByText(/Совпало/)).not.toBeInTheDocument();
  });
});

describe("MatchEvidence: поля есть — блок показан", () => {
  it("подпись со знаменателем и строка про публикации по теме", () => {
    render(<MatchEvidence result={WITH_EVIDENCE} />);
    expect(
      screen.getByText("Совпало 3 из 4 тем запроса · по публикациям OpenAlex"),
    ).toBeInTheDocument();
    expect(screen.getByText("14 публикаций по теме с 2021")).toBeInTheDocument();
  });

  it("полоса — M сегментов, N залиты акцентом", () => {
    const { container } = render(<MatchEvidence result={WITH_EVIDENCE} />);
    const segments = [...container.querySelectorAll("span")];
    expect(segments).toHaveLength(4);
    expect(segments.filter((s) => s.className.includes("bg-accent"))).toHaveLength(3);
    expect(segments.filter((s) => s.className.includes("bg-border"))).toHaveLength(1);
  });

  it("без года публикаций строка остаётся без «с <год>»", () => {
    render(
      <MatchEvidence
        result={{ ...WITH_EVIDENCE, works_on_topic: { count: 1, since_year: null } }}
      />,
    );
    expect(screen.getByText("1 публикация по теме")).toBeInTheDocument();
  });

  it("у serendipity полоса — тёплым вторым акцентом", () => {
    const { container } = render(
      <MatchEvidence result={{ ...WITH_EVIDENCE, serendipity: true }} />,
    );
    const segments = [...container.querySelectorAll("span")];
    expect(segments.filter((s) => s.className.includes("bg-serendipity"))).toHaveLength(3);
  });

  it("в карточке результата блок появляется вместе с полями", () => {
    render(<SupervisorResultCard result={WITH_EVIDENCE} query="nlp" />);
    expect(
      screen.getByText("Совпало 3 из 4 тем запроса · по публикациям OpenAlex"),
    ).toBeInTheDocument();
  });
});
