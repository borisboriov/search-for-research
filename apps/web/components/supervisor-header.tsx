import { Suspense } from "react";
import { TopicLink } from "@/components/analytics-link";

import { AvatarInitials } from "@/components/avatar-initials";
import { Card } from "@/components/ui/card";
import { MatchGrade } from "@/components/match-grade";
import type { SupervisorCard } from "@/lib/types";
import { affiliationLine } from "@/lib/utils";
import { topicLabel } from "@/lib/topics";

/** Шапка профиля: аватар, ФИО, вуз · должность, чипы тем; совпадение с
 * запросом — словесный грейд, клиентский островок (виден только при переходе
 * с результатов, `?score=&grade=`). Процента на профиле нет (решение 11.09), а с 12.09 — и в tooltip бейджа. */
export function SupervisorHeader({ card }: { card: SupervisorCard }) {
  return (
    <Card className="flex flex-col gap-3.5 p-5 sm:flex-row sm:items-center sm:gap-6 sm:px-7 sm:py-6">
      <div className="flex items-start justify-between gap-3 sm:contents">
        <AvatarInitials
          name={card.name}
          className="size-14 text-[20px] sm:order-first sm:size-[72px] sm:text-[26px]"
        />
        <Suspense>
          <MatchGrade className="sm:order-last sm:self-center" />
        </Suspense>
      </div>
      <div className="flex min-w-0 grow flex-col gap-2.5">
        <h1 className="font-display text-[26px] leading-tight font-semibold tracking-[-0.01em] sm:text-[34px]">
          {card.name}
        </h1>
        <p className="text-[14px] text-fg-muted sm:text-[16px]">
          {affiliationLine(card.institution, card.position)}
        </p>
        {card.topics.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="Ключевые темы">
            {card.topics.slice(0, 5).map((topic) => (
              <li key={topic} className="max-w-full">
                <TopicLink
                  topic={topic}
                  className="block rounded-full bg-bg-muted px-3 py-1 text-[12.5px] leading-[1.4] break-words text-fg-muted hover:text-accent focus-visible:outline-2 focus-visible:outline-accent sm:text-[13px]"
                >
                  {topicLabel(topic)}
                </TopicLink>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
