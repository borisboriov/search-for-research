import Link from "next/link";

import { AvatarInitials } from "@/components/avatar-initials";
import { MatchBadge } from "@/components/match-badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { MatchResult, SupervisorCard as SupervisorCardData } from "@/lib/types";
import { affiliationLine, formatNumber, pluralize } from "@/lib/utils";

function metaWorksCount(count: number | null): string | null {
  if (count === null) return null;
  return `${formatNumber(count)} ${pluralize(count, "публикация", "публикации", "публикаций")}`;
}

/**
 * Карточка в списке результатов. Десктоп — горизонтальная с кнопкой «Открыть
 * профиль»; мобайл — вертикальная, кликабельна целиком (SPEC_SFR3 §2).
 */
export function SupervisorResultCard({ result, query }: { result: MatchResult; query: string }) {
  const href = `/supervisor/${result.author_id}?score=${result.score.toFixed(4)}&q=${encodeURIComponent(query)}`;
  const lastWork = result.top_works[0];
  return (
    <Card className="relative flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:gap-5 sm:px-6 sm:py-[22px]">
      <div className="flex items-start justify-between gap-2.5 sm:contents">
        <div className="flex items-center gap-2.5 sm:hidden">
          <AvatarInitials name={result.name} serendipity={result.serendipity} className="size-[42px] text-[15px]" />
          <span className="flex flex-col gap-0.5">
            <span className="text-[15px] font-semibold">{result.name}</span>
            <span className="text-[13px] text-fg-muted">
              {affiliationLine(result.institution, result.position)}
            </span>
          </span>
        </div>
        <MatchBadge score={result.score} serendipity={result.serendipity} className="sm:hidden" />
      </div>

      <AvatarInitials
        name={result.name}
        serendipity={result.serendipity}
        className="hidden size-[52px] text-[18px] sm:flex"
      />
      <div className="flex grow flex-col gap-2">
        <div className="hidden items-center gap-3 sm:flex">
          <span className="text-[17px] font-semibold">{result.name}</span>
          <span className="text-[14px] text-fg-muted">
            {affiliationLine(result.institution, result.position)}
          </span>
        </div>
        {result.serendipity && (
          <p className="text-[13px] text-serendipity">
            Смежная область, которая может расширить тему
          </p>
        )}
        <p className="text-[14px] leading-normal text-fg-muted sm:text-[15px]">
          {result.topics.slice(0, 3).join(", ")}
        </p>
        <p className="flex flex-wrap gap-x-3.5 gap-y-1 text-[12px] text-fg-subtle sm:gap-x-[18px] sm:text-[13px]">
          {result.h_index !== null && <span>h-index {result.h_index}</span>}
          {metaWorksCount(result.works_count) && <span>{metaWorksCount(result.works_count)}</span>}
          {lastWork && (
            <span className="hidden lg:inline">
              Последняя: {lastWork.title}
              {lastWork.year ? ` · ${lastWork.year}` : ""}
            </span>
          )}
        </p>
      </div>
      <div className="hidden shrink-0 flex-col items-end gap-3 sm:flex">
        <MatchBadge score={result.score} serendipity={result.serendipity} />
        <Link
          href={href}
          className="rounded-btn border border-border bg-surface px-4 py-2.5 text-[14px] font-medium whitespace-nowrap hover:bg-bg focus-visible:outline-2 focus-visible:outline-accent"
        >
          Открыть профиль
        </Link>
      </div>
      {/* Мобайл: кликабельна вся карточка (растянутая ссылка поверх). */}
      <Link href={href} aria-label={`Открыть профиль: ${result.name}`} className="absolute inset-0 sm:hidden" />
    </Card>
  );
}

/**
 * Превью на лендинге: данные реальные, запроса нет — поэтому без бейджа «NN%»
 * (расхождение с макетом зафиксировано в отчёте: выдуманный процент хуже пустого угла).
 */
export function SupervisorPreviewCard({ card }: { card: SupervisorCardData }) {
  return (
    <Card className="flex flex-col gap-3 p-4 sm:gap-3.5 sm:p-[22px]">
      <div className="flex items-center gap-2.5 sm:gap-3">
        <AvatarInitials name={card.name} className="size-[42px] text-[15px] sm:size-11 sm:text-[16px]" />
        <span className="flex flex-col gap-0.5">
          <span className="text-[15px] font-semibold sm:text-[16px]">{card.name}</span>
          <span className="text-[13px] text-fg-muted">
            {affiliationLine(card.institution, card.position)}
          </span>
        </span>
      </div>
      <p className="text-[14px] leading-normal text-fg-muted">{card.topics.slice(0, 3).join(", ")}</p>
      <p className="flex gap-3.5 text-[12px] text-fg-subtle sm:gap-4 sm:text-[13px]">
        {card.h_index !== null && <span>h-index {card.h_index}</span>}
        {metaWorksCount(card.works_count) && <span>{metaWorksCount(card.works_count)}</span>}
      </p>
    </Card>
  );
}

/** Скелетон на время запроса к /match (p50 0,6 с, до 2 с — индикатор обязателен). */
export function SupervisorCardSkeleton() {
  return (
    <Card aria-hidden className="flex items-center gap-5 p-4 sm:px-6 sm:py-[22px]">
      <Skeleton className="size-[42px] rounded-full sm:size-[52px]" />
      <div className="flex grow flex-col gap-2.5">
        <Skeleton className="h-4 w-2/5" />
        <Skeleton className="h-3.5 w-4/5" />
        <Skeleton className="h-3 w-3/5" />
      </div>
      <Skeleton className="hidden h-8 w-14 sm:block" />
    </Card>
  );
}
