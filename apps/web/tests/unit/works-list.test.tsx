import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { abstractFragments, WorksList } from "@/components/works-list";
import type { SupervisorCard } from "@/lib/types";
import { worksByYear } from "@/lib/works";

const CARD: SupervisorCard = {
  author_id: "A1", name: "Author", institution: null, position: null,
  h_index: null, works_count: 24, topics: [], profile_text: "", cited_by_count: null,
  email: null, serendipity: false,
  top_works: [
    { title: "Old highly cited work", year: 2001 },
    { title: "Undated first", year: null },
    { title: "Recent work first", year: 2025 },
    { title: "Recent work second", year: 2025 },
    { title: "Undated second", year: null },
  ],
};

describe("abstractFragments", () => {
  it("достаёт фрагменты аннотаций из строк profile_text", () => {
    const text = [
      "Ivan Smirnov — МФТИ. h-index: 13.",
      "Ключевые темы: NLP; Topic Modeling.",
      "«Depression detection» (2023). We study social media posts…",
      "«Без аннотации» (2021).",
    ].join("\n");
    const fragments = abstractFragments(text);
    expect(fragments.get("Depression detection")).toBe("We study social media posts…");
    expect(fragments.has("Без аннотации")).toBe(false);
  });
});

describe("worksByYear / WorksList", () => {
  it("сортирует по убыванию года; неизвестные в конце, одинаковые годы стабильны", () => {
    const original = [...CARD.top_works];
    expect(worksByYear(CARD.top_works).map((work) => work.title)).toEqual([
      "Recent work first", "Recent work second", "Old highly cited work", "Undated first", "Undated second",
    ]);
    expect(CARD.top_works).toEqual(original);
  });
  it("подпись объясняет отбор и порядок, все работы отображены без перевода", () => {
    render(<WorksList card={CARD} />);
    expect(screen.getByRole("heading", { name: "Выбранные работы" })).toBeInTheDocument();
    expect(screen.getByText(/не полный список/)).toBeInTheDocument();
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Recent work first");
    expect(rows[1]).toHaveTextContent("Recent work second");
    expect(rows[2]).toHaveTextContent("Old highly cited work");
    expect(rows[3]).toHaveTextContent("Undated firstгод не указан");
    expect(rows[4]).toHaveTextContent("Undated secondгод не указан");
  });
  it("без работ блок скрыт", () => {
    const { container } = render(<WorksList card={{ ...CARD, top_works: [] }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
