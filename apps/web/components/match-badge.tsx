import { cn } from "@/lib/utils";
import { matchPercent } from "@/lib/utils";

/** «NN%» или «неожиданный вариант» (единственное применение --serendipity). */
export function MatchBadge({
  score,
  serendipity = false,
  className,
}: {
  score: number;
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
    <span
      className={cn(
        "rounded-badge bg-accent-soft px-[11px] py-1.5 text-[15px] font-semibold whitespace-nowrap text-accent",
        className,
      )}
    >
      {matchPercent(score)}
    </span>
  );
}
