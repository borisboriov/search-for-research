import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { MatchBadge } from "@/components/match-badge";
import { WeakBanner } from "@/components/empty-results";
import { GRADE_LABELS } from "@/lib/utils";

// SPEC_SFR4 §0.9: словесные грейды вместо процента.
// Решение 13.09 (SPEC_SFR6 §0 «процент нигде»): процента нет и в tooltip —
// tooltip убран целиком, бейдж больше не фокусируется и ничего не раскрывает.

describe("MatchBadge", () => {
  it.each([
    ["high", "высокое совпадение"],
    ["medium", "среднее совпадение"],
    ["low", "слабое совпадение"],
  ] as const)("грейд %s → «%s», без процента на бейдже", (grade, label) => {
    render(<MatchBadge grade={grade} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.queryByText("38%")).not.toBeInTheDocument();
  });

  it("процента нет ни в разметке бейджа, ни при наведении", async () => {
    const user = userEvent.setup();
    const { container } = render(<MatchBadge grade="medium" />);
    const badge = screen.getByText(GRADE_LABELS.medium);
    await user.hover(badge);
    expect(container.textContent).not.toMatch(/%/);
    expect(document.body.textContent).not.toMatch(/Косинусная близость/);
    // Бейдж больше не триггер: фокусировать нечего, раскрывать нечего
    expect(badge).not.toHaveAttribute("tabindex");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("serendipity перекрывает грейд", () => {
    render(<MatchBadge grade="medium" serendipity />);
    expect(screen.getByText("неожиданный вариант")).toBeInTheDocument();
    expect(screen.queryByText(GRADE_LABELS.medium)).not.toBeInTheDocument();
  });
});

describe("WeakBanner", () => {
  it("текст серой зоны — подсказка, не отказ", () => {
    render(<WeakBanner />);
    expect(
      screen.getByText(/Совпадения слабые — похоже, в базе пока нет специалистов/),
    ).toBeInTheDocument();
  });

  // Сквозное обращение интерфейса — «ты»; баннер был единственным местом на «вы»
  it("обращается на «ты»", () => {
    const { container } = render(<WeakBanner />);
    expect(container.textContent).toContain("Попробуй ");
    expect(container.textContent).not.toContain("Попробуйте");
  });
});
