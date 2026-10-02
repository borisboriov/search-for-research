import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { GRADE_EXPLANATIONS, MatchBadge, MATCH_EXPLANATION } from "@/components/match-badge";
import { WeakBanner } from "@/components/empty-results";
import { GRADE_LABELS } from "@/lib/utils";

// Нативные details не зависят от hover: доступны на телефоне и с клавиатуры.
describe("MatchBadge", () => {
  it.each(["high", "medium", "low"] as const)("грейд %s раскрывает объяснение без численных оценок", async (grade) => {
    const user = userEvent.setup();
    const { container } = render(<MatchBadge grade={grade} />);
    const summary = screen.getByLabelText(`${GRADE_LABELS[grade]}: что это значит`);
    expect(screen.getByText(GRADE_LABELS[grade])).toBeInTheDocument();
    expect(container.querySelector("details")).not.toHaveAttribute("open");
    await user.click(summary);
    expect(container.querySelector("details")).toHaveAttribute("open");
    expect(screen.getByText(GRADE_EXPLANATIONS[grade])).toBeInTheDocument();
    expect(screen.getByText(MATCH_EXPLANATION)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/%|cosine|косинус|0[.,]\d/);
    await user.click(summary);
    expect(container.querySelector("details")).not.toHaveAttribute("open");
  });

  it("serendipity объясняется как смежная область", async () => {
    const user = userEvent.setup();
    render(<MatchBadge grade="medium" serendipity />);
    await user.click(screen.getByLabelText("неожиданный вариант: что это значит"));
    expect(screen.getByText(/Неожиданный вариант: исследователь из смежной области/)).toBeInTheDocument();
    expect(screen.queryByText(GRADE_LABELS.medium)).not.toBeInTheDocument();
  });
});

describe("WeakBanner", () => {
  it("объясняет слабость без вывода об отсутствии специалистов и даёт три совета", () => {
    const { container } = render(<WeakBanner />);
    expect(screen.getByText(/Совпадения слабые: запрос мало похож/)).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(container.textContent).not.toContain("нет специалистов");
    expect(container.textContent).toContain("Попробуй ");
  });

  it("действие открывает редактирование", async () => {
    const user = userEvent.setup();
    const onEditQuery = vi.fn();
    render(<WeakBanner onEditQuery={onEditQuery} />);
    await user.click(screen.getByRole("button", { name: "Изменить запрос" }));
    expect(onEditQuery).toHaveBeenCalledOnce();
  });
});
