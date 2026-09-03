import { Suspense } from "react";

import { AvatarInitials } from "@/components/avatar-initials";
import { Card } from "@/components/ui/card";
import { MatchScore } from "@/components/match-score";
import type { SupervisorCard } from "@/lib/types";
import { affiliationLine } from "@/lib/utils";

/** Шапка профиля: аватар, ФИО, вуз · должность, чипы тем; блок совпадения —
 * клиентский островок (виден только при переходе с результатов, ?score=). */
export function SupervisorHeader({ card }: { card: SupervisorCard }) {
  return (
    <Card className="flex flex-col gap-3.5 rounded-search p-5 sm:flex-row sm:items-center sm:gap-6 sm:px-8 sm:py-7">
      <div className="flex items-start justify-between gap-3 sm:contents">
        <AvatarInitials
          name={card.name}
          className="size-14 text-[20px] sm:order-first sm:size-[84px] sm:text-[30px]"
        />
        <Suspense>
          <MatchScore className="sm:order-last" />
        </Suspense>
      </div>
      <div className="flex grow flex-col gap-2.5">
        <h1 className="font-display text-[24px] leading-tight font-semibold tracking-[-0.01em] sm:text-[32px]">
          {card.name}
        </h1>
        <p className="text-[14px] text-fg-muted sm:text-[16px]">
          {affiliationLine(card.institution, card.position)}
        </p>
        {card.topics.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="Ключевые темы">
            {card.topics.slice(0, 5).map((topic) => (
              <li
                key={topic}
                className="rounded-full bg-accent-soft px-3 py-[7px] text-[13px] font-medium whitespace-nowrap text-accent sm:text-[14px]"
              >
                {topic}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
