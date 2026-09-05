import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { MatchBadge } from "@/components/match-badge";
import { WeakBanner } from "@/components/empty-results";
import { GRADE_LABELS } from "@/lib/utils";

// SPEC_SFR4 §0.9: словесные грейды вместо процента, процент — в tooltip.

describe("MatchBadge", () => {
  it.each([
    ["high", "высокое совпадение"],
    ["medium", "среднее совпадение"],
    ["low", "слабое совпадение"],
  ] as const)("грейд %s → «%s», без процента на бейдже", (grade, label) => {
    render(<MatchBadge score={0.38} grade={grade} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.queryByText("38%")).not.toBeInTheDocument();
  });

  it("процент показывается в tooltip при наведении", async () => {
    const user = userEvent.setup();
    render(<MatchBadge score={0.38} grade="medium" />);
    await user.hover(screen.getByText(GRADE_LABELS.medium));
    const tooltip = await screen.findAllByText(/Косинусная близость с запросом: 38%/);
    expect(tooltip.length).toBeGreaterThan(0);
  });

  it("serendipity перекрывает грейд", () => {
    render(<MatchBadge score={0.38} grade="medium" serendipity />);
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
});
