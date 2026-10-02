import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  SupervisorCardSkeleton,
  SupervisorPreviewCard,
  SupervisorResultCard,
} from "@/components/supervisor-card";
import type { MatchResult } from "@/lib/types";
import { topicLabel } from "@/lib/topics";

vi.mock("next/link", () => ({
  default: ({ prefetch, ...props }: ComponentProps<"a"> & { prefetch?: boolean }) =>
    <a {...props} data-prefetch={String(prefetch)} />,
}));

const LONG_TITLE =
  "RussianSuperGLUE: A Russian Language Understanding Evaluation Benchmark for Neural Models";

const RESULT: MatchResult = {
  author_id: "A1",
  name: "Ivan Smirnov",
  institution: "Московский физико-технический институт",
  h_index: 13,
  works_count: 88,
  topics: ["NLP", "Mental Health via Writing", "Topic Modeling", "лишняя тема", "пятая тема"],
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
  it("показывает имя, организацию, h-index и словесный грейд — без процента", () => {
    render(<SupervisorResultCard result={RESULT} query="nlp" />);
    expect(screen.getByText("Ivan Smirnov")).toBeInTheDocument();
    expect(screen.getByText("МФТИ")).toBeInTheDocument();
    expect(screen.getByText("h-index 13")).toBeInTheDocument();
    // Грейд словами на бейдже; процента нет нигде (SPEC_SFR4 §0.9, решение 13.09)
    expect(screen.getByText("высокое совпадение")).toBeInTheDocument();
    expect(screen.queryByText("43%")).not.toBeInTheDocument();
  });

  it("темы — отдельными пилюлями, не более четырёх (P-06: текст пилюли не режем)", () => {
    render(<SupervisorResultCard result={RESULT} query="nlp" />);
    const pills = screen.getByRole("list", { name: "Ключевые темы" });
    expect(pills.children).toHaveLength(4);
    expect(screen.getByText(topicLabel("Mental Health via Writing"))).toBeInTheDocument();
    expect(screen.queryByText("пятая тема")).not.toBeInTheDocument();
  });

  it("ссылки ведут на профиль и передают score, грейд и запрос", () => {
    render(<SupervisorResultCard result={RESULT} query="анализ текстов" />);
    const links = screen.getAllByRole("link", { name: /Открыть профиль/ });
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      expect(link).toHaveAttribute(
        "href",
        expect.stringContaining("/supervisor/A1?score=0.4321&grade=high"),
      );
      expect(link.getAttribute("href")).toContain(encodeURIComponent("анализ текстов"));
    }
  });

  it("темы ведут на поиск с исходным названием, даже если отображается перевод", () => {
    render(<SupervisorResultCard result={RESULT} query="nlp" />);
    const topic = screen.getByRole("link", { name: topicLabel("Topic Modeling") });
    expect(topic).toHaveAttribute("href", `/results?q=${encodeURIComponent("Topic Modeling")}`);
    expect(topic).toHaveAttribute("rel", "nofollow");
    expect(topic).toHaveAttribute("data-prefetch", "false");
    expect(topic).toHaveClass("relative", "z-10");
  });

  it("неизвестная тема сохраняет исходное название и корректно кодируется в URL", () => {
    render(<SupervisorResultCard result={{ ...RESULT, topics: ["Unknown / A&B"] }} query="nlp" />);
    const topic = screen.getByRole("link", { name: "Unknown / A&B" });
    expect(topic).toHaveAttribute("href", "/results?q=Unknown%20%2F%20A%26B");
  });

  it("должность не показывается, когда поля нет, и появляется, когда есть", () => {
    const { unmount } = render(<SupervisorResultCard result={RESULT} query="nlp" />);
    expect(screen.queryByText("профессор")).not.toBeInTheDocument();
    unmount();
    render(<SupervisorResultCard result={{ ...RESULT, position: "профессор" }} query="nlp" />);
    expect(screen.getByText("профессор")).toBeInTheDocument();
  });
});

describe("SupervisorResultCard: последняя работа (P-15)", () => {
  it("показывает самую свежую среди выбранных с честной подписью", () => {
    render(<SupervisorResultCard result={{ ...RESULT, top_works: [
      { title: "Old highly cited work", year: 2001 },
      { title: "Fresh selected work", year: 2025 },
    ] }} query="nlp" />);
    expect(screen.getByText(/Fresh selected work/)).toBeInTheDocument();
    expect(screen.getByText(/Выбранная работа · 2025/)).toBeInTheDocument();
    expect(screen.queryByText(/Old highly cited work/)).not.toBeInTheDocument();
  });
  it("короткое название показывается целиком, ссылки «раскрыть» нет", () => {
    render(<SupervisorResultCard result={RESULT} query="nlp" />);
    expect(screen.getByText(/Depression detection/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "раскрыть" })).not.toBeInTheDocument();
  });

  it("длинное — обрезается и раскрывается по клику", async () => {
    const user = userEvent.setup();
    render(
      <SupervisorResultCard
        result={{ ...RESULT, top_works: [{ title: LONG_TITLE, year: 2020 }] }}
        query="nlp"
      />,
    );
    expect(screen.queryByText(LONG_TITLE)).not.toBeInTheDocument();
    expect(screen.getByText(/RussianSuperGLUE: A Russian Language Understanding Evaluation…/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "раскрыть" }));
    expect(screen.getByText(LONG_TITLE)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "свернуть" })).toBeInTheDocument();
  });
});

describe("SupervisorResultCard: serendipity", () => {
  it("бейдж «неожиданный вариант» вместо грейда и строка «Почему в подборке»", () => {
    render(<SupervisorResultCard result={{ ...RESULT, serendipity: true }} query="nlp" />);
    expect(screen.getByText("неожиданный вариант")).toBeInTheDocument();
    expect(screen.queryByText("высокое совпадение")).not.toBeInTheDocument();
    expect(screen.getByText("Почему в подборке:")).toBeInTheDocument();
  });
});

describe("SupervisorPreviewCard (компактный вариант лендинга)", () => {
  it("ссылка темы доступна поверх растянутой ссылки профиля", () => {
    render(<SupervisorPreviewCard card={RESULT} />);
    const topic = screen.getByRole("link", { name: topicLabel("NLP") });
    expect(topic).toHaveClass("relative", "z-10");
    expect(topic).toHaveAttribute("href", "/results?q=NLP");
  });
  it("без бейджа и без полосы совпадения — запроса нет, считать нечего", () => {
    render(<SupervisorPreviewCard card={RESULT} />);
    expect(screen.getByText("Ivan Smirnov")).toBeInTheDocument();
    expect(screen.queryByText("высокое совпадение")).not.toBeInTheDocument();
    expect(screen.queryByText(/Совпало/)).not.toBeInTheDocument();
  });
});

describe("SupervisorCardSkeleton", () => {
  it("рендерится и скрыт от скринридеров (декорация на время загрузки)", () => {
    const { container } = render(<SupervisorCardSkeleton />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });
});
