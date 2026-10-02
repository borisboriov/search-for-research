import { CircleHelp } from "lucide-react";

import type { Grade } from "@/lib/types";
import { cn, gradeLabel } from "@/lib/utils";

export const GRADE_EXPLANATIONS: Record<Grade, string> = {
  high: "Высокое совпадение: по оценке поиска описание исследователя близко к твоему запросу.",
  medium: "Среднее совпадение: по оценке поиска описание исследователя частично близко к твоему запросу.",
  low: "Слабое совпадение: по оценке поиска описание исследователя мало похоже на твой запрос.",
};

export const MATCH_EXPLANATION =
  "Поиск сравнивает твой запрос с описанием исследователя, составленным по публикациям OpenAlex. Степень совпадения помогает выбрать, какие профили изучить. Он не подтверждает готовность исследователя руководить твоей работой. Проверь темы и публикации в профиле.";

/** Нативное раскрытие работает с клавиатуры и на телефоне, в том числе в SSR.
 * Грейд приходит из API; численные оценки и границы фронт не показывает. */
export function MatchBadge({
  grade,
  serendipity = false,
  className,
}: {
  grade: Grade;
  serendipity?: boolean;
  className?: string;
}) {
  const label = serendipity ? "неожиданный вариант" : gradeLabel(grade);
  return (
    <details className={cn("relative z-10 min-w-0 max-w-full sm:max-w-[300px]", className)}>
      <summary
        aria-label={`${label}: что это значит`}
        className={cn(
          "flex min-h-11 w-fit cursor-pointer list-none items-center gap-1.5 rounded-badge px-2.5 py-1 text-[13px] font-medium whitespace-nowrap focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden",
          serendipity
            ? "bg-serendipity-soft text-serendipity"
            : "bg-accent-soft text-accent",
        )}
      >
        <span>{label}</span>
        <CircleHelp className="size-3.5 shrink-0" aria-hidden strokeWidth={2} />
      </summary>
      <div className="mt-2 w-[280px] max-w-full rounded-btn border border-border bg-surface p-3 text-[13px] leading-relaxed text-fg-muted">
        <p>
          {serendipity
            ? "Неожиданный вариант: исследователь из смежной области, который может расширить твою тему."
            : GRADE_EXPLANATIONS[grade]}
        </p>
        <p className="mt-2">{MATCH_EXPLANATION}</p>
      </div>
    </details>
  );
}
