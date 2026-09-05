import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  SupervisorCardSkeleton,
  SupervisorResultCard,
} from "@/components/supervisor-card";
import type { MatchResult } from "@/lib/types";

const RESULT: MatchResult = {
  author_id: "A1",
  name: "Ivan Smirnov",
  institution: "Московский физико-технический институт",
  h_index: 13,
  works_count: 88,
  topics: ["NLP", "Mental Health via Writing", "Topic Modeling", "лишняя тема"],
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

describe("SupervisorResultCard: обычное состояние", () => {
  it("показывает имя, вуз, словесный грейд (не процент) и первые три темы", () => {
    render(<SupervisorResultCard result={RESULT} query="nlp" />);
    expect(screen.getAllByText("Ivan Smirnov").length).toBeGreaterThan(0);
    expect(screen.getAllByText("МФТИ")[0]).toBeInTheDocument();
    // Грейд словами на бейдже; процент — только в tooltip (SPEC_SFR4 §0.9)
    expect(screen.getAllByText("высокое совпадение")[0]).toBeInTheDocument();
    expect(screen.queryByText("43%")).not.toBeInTheDocument();
    expect(
      screen.getByText("NLP, Mental Health via Writing, Topic Modeling"),
    ).toBeInTheDocument();
  });
  it("ссылки ведут на профиль и передают score и запрос", () => {
    render(<SupervisorResultCard result={RESULT} query="анализ текстов" />);
    const links = screen.getAllByRole("link");
    for (const link of links) {
      expect(link).toHaveAttribute(
        "href",
        expect.stringContaining("/supervisor/A1?score=0.4321"),
      );
      expect(link.getAttribute("href")).toContain(encodeURIComponent("анализ текстов"));
    }
  });
});

describe("SupervisorResultCard: serendipity", () => {
  it("бейдж «неожиданный вариант» вместо процента и пояснение", () => {
    render(
      <SupervisorResultCard result={{ ...RESULT, serendipity: true }} query="nlp" />,
    );
    expect(screen.getAllByText("неожиданный вариант")[0]).toBeInTheDocument();
    expect(screen.queryByText("высокое совпадение")).not.toBeInTheDocument();
    expect(
      screen.getByText("Смежная область, которая может расширить тему"),
    ).toBeInTheDocument();
  });
});

describe("SupervisorCardSkeleton", () => {
  it("рендерится и скрыт от скринридеров (декорация на время загрузки)", () => {
    const { container } = render(<SupervisorCardSkeleton />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });
});
