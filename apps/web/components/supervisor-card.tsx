import { BarChart3, Building2, User } from "lucide-react";
import Link from "next/link";

import { AvatarInitials } from "@/components/avatar-initials";
import { MatchBadge } from "@/components/match-badge";
import { LastWork } from "@/components/last-work";
import { MatchEvidence } from "@/components/match-evidence";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { MatchResult, SupervisorCard as SupervisorCardData } from "@/lib/types";
import { cn, institutionShort } from "@/lib/utils";
import { topicLabel } from "@/lib/topics";
import { worksByYear } from "@/lib/works";

/** Темы — серые пилюли с переносом, текст внутри пилюли не обрезается (P-06).
 * Показываем до четырёх: столько же в самой плотной карточке макета B. */
const TOPICS_SHOWN = 4;

function TopicPills({ topics }: { topics: string[] }) {
  if (topics.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Ключевые темы">
      {topics.slice(0, TOPICS_SHOWN).map((topic) => (
        <li key={topic} className="max-w-full">
          <Link
            href={`/results?q=${encodeURIComponent(topic)}`}
            prefetch={false}
            rel="nofollow"
            className="relative z-10 block rounded-full bg-bg-muted px-2.5 py-[3px] text-[12.5px] leading-[1.4] break-words text-fg-muted hover:text-accent focus-visible:outline-2 focus-visible:outline-accent"
          >
            {topicLabel(topic)}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Ярус фактов: организация, должность (только если поле есть) и h-index —
 * иконками lucide вместо строки «МФТИ · профессор» (DESIGN_SYSTEM v2 §4). */
function FactsRow({
  institution,
  position,
  hIndex,
}: {
  institution: string | null;
  position: string | null;
  hIndex: number | null;
}) {
  const university = institutionShort(institution);
  if (university === null && position === null && hIndex === null) return null;
  return (
    <div className="flex flex-wrap gap-x-3.5 gap-y-1.5 text-[13px] text-fg-muted">
      {university !== null && (
        <span className="inline-flex items-center gap-1.5">
          <Building2 className="size-3.5 shrink-0 text-fg-subtle" aria-hidden strokeWidth={2} />
          {university}
        </span>
      )}
      {position !== null && (
        <span className="inline-flex items-center gap-1.5">
          <User className="size-3.5 shrink-0 text-fg-subtle" aria-hidden strokeWidth={2} />
          {position}
        </span>
      )}
      {hIndex !== null && (
        <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
          <BarChart3 className="size-3.5 shrink-0 text-fg-subtle" aria-hidden strokeWidth={2} />
          h-index {hIndex}
        </span>
      )}
    </div>
  );
}

/**
 * Карточка в списке результатов, v2 (DESIGN_SYSTEM §4). Десктоп — аватар
 * слева, ярусы справа, кнопка «Открыть профиль» внизу справа; мобайл —
 * вертикальная, кликабельна целиком, кнопки нет.
 */
export function SupervisorResultCard({ result, query }: { result: MatchResult; query: string }) {
  const href = `/supervisor/${result.author_id}?score=${result.score.toFixed(4)}&grade=${
    result.serendipity ? "serendipity" : result.grade
  }&q=${encodeURIComponent(query)}`;
  const lastWork = worksByYear(result.top_works)[0];
  return (
    <Card
      className={cn(
        "relative flex flex-col gap-2.5 p-4 sm:flex-row sm:items-start sm:gap-4 sm:p-5",
        // Рамка `--serendipity` — единственный второй акцент интерфейса
        result.serendipity && "border-serendipity",
      )}
    >
      {/* Десктоп: аватар — слева от всей колонки; мобайл: он в строке с именем,
          иначе ярусы уезжают вправо на 52px из 390 (макет B, 390). */}
      <AvatarInitials
        name={result.name}
        serendipity={result.serendipity}
        className="hidden size-11 text-[16px] sm:flex"
      />
      <div className="flex min-w-0 grow flex-col gap-2.5">
        {/* Десктоп: имя и бейдж в одной строке; мобайл: бейдж под именем */}
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <AvatarInitials
              name={result.name}
              serendipity={result.serendipity}
              className="size-10 text-[14px] sm:hidden"
            />
            <h3 className="font-display text-[20px] leading-tight font-semibold tracking-[-0.01em] sm:text-[22px]">
              {result.name}
            </h3>
          </div>
          <MatchBadge
            grade={result.grade}
            serendipity={result.serendipity}
            className="self-start"
          />
        </div>
        <FactsRow
          institution={result.institution}
          position={result.position}
          hIndex={result.h_index}
        />
        <MatchEvidence result={result} />
        {result.serendipity && (
          <p className="text-[14px] leading-[1.45] text-fg-muted">
            <span className="font-medium text-serendipity">Почему в подборке:</span> смежная
            область, которая может расширить тему
          </p>
        )}
        <TopicPills topics={result.topics} />
        {lastWork && <LastWork work={lastWork} />}
        <div className="hidden justify-end pt-0.5 sm:flex">
          <Link
            href={href}
            className="relative z-10 inline-flex min-h-11 items-center rounded-btn border border-border bg-surface px-[18px] py-2.5 text-[15px] font-medium whitespace-nowrap hover:bg-bg focus-visible:outline-2 focus-visible:outline-accent"
          >
            Открыть профиль
          </Link>
        </div>
      </div>
      {/* Мобайл: кликабельна вся карточка (растянутая ссылка поверх). */}
      <Link href={href} aria-label={`Открыть профиль: ${result.name}`} className="absolute inset-0 sm:hidden" />
    </Card>
  );
}

/**
 * Превью на лендинге: компактный вариант карточки (v2 §4) — мобильная
 * раскладка без кнопки, вся карточка ссылка. Запроса нет, поэтому нет ни
 * бейджа грейда, ни полосы совпадения: выдуманный процент хуже пустого угла
 * (расхождение с макетом зафиксировано ещё в SFR3_REPORT).
 */
export function SupervisorPreviewCard({ card }: { card: SupervisorCardData }) {
  const lastWork = worksByYear(card.top_works)[0];
  return (
    <Card className="relative flex flex-col gap-2.5 p-4">
      <div className="flex items-center gap-3">
        <AvatarInitials name={card.name} className="size-10 text-[14px]" />
        <h3 className="min-w-0 font-display text-[20px] leading-tight font-semibold tracking-[-0.01em]">
          {card.name}
        </h3>
      </div>
      <FactsRow institution={card.institution} position={card.position} hIndex={card.h_index} />
      <TopicPills topics={card.topics} />
      {lastWork && <LastWork work={lastWork} />}
      <Link
        href={`/supervisor/${card.author_id}`}
        aria-label={`Открыть профиль: ${card.name}`}
        className="absolute inset-0 rounded-card focus-visible:outline-2 focus-visible:outline-accent"
      />
    </Card>
  );
}

/** Скелетон на время запроса к /match (p50 0,6 с, до 2 с — индикатор обязателен). */
export function SupervisorCardSkeleton() {
  return (
    <Card aria-hidden className="flex items-start gap-3 p-4 sm:gap-4 sm:p-5">
      <Skeleton className="size-10 shrink-0 rounded-full sm:size-11" />
      <div className="flex grow flex-col gap-2.5">
        <Skeleton className="h-5 w-2/5" />
        <Skeleton className="h-3.5 w-3/5" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-3.5 w-1/2" />
      </div>
    </Card>
  );
}
