"use client";

import { useSearchParams } from "next/navigation";

import { cn, matchPercent } from "@/lib/utils";

/**
 * Блок «NN% совпадение» — только при переходе с результатов (query-параметр
 * score). Клиентский островок: чтение searchParams в серверном компоненте
 * сделало бы страницу динамической и убило бы ISR (docs/DECISIONS.md).
 */
export function MatchScore({ className }: { className?: string }) {
  const params = useSearchParams();
  const raw = params.get("score");
  const score = raw === null ? NaN : Number(raw);
  if (!Number.isFinite(score) || score <= 0 || score > 1) return null;
  return (
    <div
      className={cn(
        "flex shrink-0 flex-col items-center gap-1 rounded-card bg-accent-soft px-3.5 py-2.5 sm:px-[22px] sm:py-4",
        className,
      )}
    >
      <span className="font-display text-[26px] font-semibold text-accent sm:text-[36px]">
        {matchPercent(score)}
      </span>
      <span className="text-center text-[11px] text-accent sm:text-[13px]">
        совпадение
        <span className="hidden sm:inline">
          <br />с твоим запросом
        </span>
      </span>
    </div>
  );
}
