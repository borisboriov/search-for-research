import type { Grade } from "@/lib/types";
import { cn, gradeLabel } from "@/lib/utils";

/**
 * Словесный грейд («высокое/среднее/слабое совпадение») или «неожиданный
 * вариант» (единственное применение --serendipity). Живые косинусные 30–45%
 * читались как «плохой сервис», слова честнее передают смысл шкалы
 * (SPEC_SFR4 §0.9, решение Бориса 05.09).
 *
 * Процента здесь нет вовсе. До 12.09 он оставался в tooltip бейджа — и вместе
 * с переездом бейджа на страницу НР (SFR-6) снова стал достижим в интерфейсе,
 * вопреки требованию «процент нигде» (SPEC_SFR6 §0). Решение Бориса 12.09:
 * tooltip убран целиком, а не заменён другим текстом — нового текста на
 * страницах итерация не заводит. Сам грейд считает API: границы шкалы фронт
 * не знает и косинус больше нигде не показывает.
 */
export function MatchBadge({
  grade,
  serendipity = false,
  className,
}: {
  grade: Grade;
  serendipity?: boolean;
  className?: string;
}) {
  if (serendipity) {
    return (
      <span
        className={cn(
          "inline-flex rounded-badge bg-serendipity-soft px-2.5 py-1 text-[13px] font-medium whitespace-nowrap text-serendipity",
          className,
        )}
      >
        неожиданный вариант
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex rounded-badge bg-accent-soft px-2.5 py-1 text-[13px] font-medium whitespace-nowrap text-accent",
        className,
      )}
    >
      {gradeLabel(grade)}
    </span>
  );
}
