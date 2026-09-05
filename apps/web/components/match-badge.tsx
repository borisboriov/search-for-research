import type { Grade } from "@/lib/types";
import { cn, gradeLabel, matchPercent } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Словесный грейд («высокое/среднее/слабое совпадение») или «неожиданный
 * вариант» (единственное применение --serendipity). Процент не исчез — он в
 * tooltip: живые косинусные 30–45% на бейдже читались как «плохой сервис»,
 * слова честнее передают смысл шкалы (SPEC_SFR4 §0.9, решение Бориса 05.09).
 * Сам грейд считает API — границы шкалы фронт не знает.
 */
export function MatchBadge({
  score,
  grade,
  serendipity = false,
  className,
}: {
  score: number;
  grade: Grade;
  serendipity?: boolean;
  className?: string;
}) {
  if (serendipity) {
    return (
      <span
        className={cn(
          "rounded-badge bg-serendipity-soft px-2.5 py-1.5 text-[12px] font-semibold whitespace-nowrap text-serendipity",
          className,
        )}
      >
        неожиданный вариант
      </span>
    );
  }
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            tabIndex={0}
            className={cn(
              "cursor-default rounded-badge bg-accent-soft px-[11px] py-1.5 text-[13px] font-semibold whitespace-nowrap text-accent",
              className,
            )}
          >
            {gradeLabel(grade)}
          </span>
        </TooltipTrigger>
        <TooltipContent>Косинусная близость с запросом: {matchPercent(score)}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
