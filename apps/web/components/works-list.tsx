import { Card } from "@/components/ui/card";
import type { SupervisorCard } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

/**
 * Названия работ — в первую очередь, аннотация — свёрнуто/вторично: эксперимент
 * SFR-2 показал, что сигнал в названиях (SPEC_SFR3 §2). Фрагменты аннотаций
 * достаются из profile_text — отдельного поля с ними в карточке нет.
 */
export function abstractFragments(profileText: string): Map<string, string> {
  const fragments = new Map<string, string>();
  for (const line of profileText.split("\n")) {
    const match = line.match(/^«(.+?)»(?: \(\d{4}\))?\.\s*(.+)$/);
    if (match && match[2]) fragments.set(match[1]!, match[2]);
  }
  return fragments;
}

export function WorksList({ card }: { card: SupervisorCard }) {
  const works = card.top_works.slice(0, 8);
  const fragments = abstractFragments(card.profile_text);
  if (works.length === 0) return null;
  return (
    <Card className="flex flex-col gap-1.5 p-[18px] sm:px-7 sm:py-[26px]">
      <div className="flex items-center justify-between pb-2">
        <h2 className="text-[16px] font-semibold sm:text-[18px]">Последние работы</h2>
        {card.works_count !== null && (
          <a
            href={`https://openalex.org/authors/${card.author_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[13px] text-accent hover:text-accent-hover sm:text-[14px]"
          >
            Все {formatNumber(card.works_count)} в OpenAlex
          </a>
        )}
      </div>
      <ul>
        {works.map((work) => {
          const fragment = fragments.get(work.title);
          return (
            <li key={`${work.title}-${work.year}`} className="border-t border-border py-3.5">
              {fragment ? (
                <details className="group">
                  <summary className="flex cursor-pointer list-none flex-col gap-1 [&::-webkit-details-marker]:hidden">
                    <span className="text-[14px] leading-snug font-medium sm:text-[15px]">
                      {work.title}
                    </span>
                    <span className="text-[13px] text-fg-subtle">
                      {work.year ?? "год не указан"} ·{" "}
                      <span className="text-accent group-open:hidden">аннотация</span>
                      <span className="hidden text-accent group-open:inline">свернуть</span>
                    </span>
                  </summary>
                  <p className="pt-2 text-[14px] leading-relaxed text-fg-muted">{fragment}</p>
                </details>
              ) : (
                <div className="flex flex-col gap-1">
                  <span className="text-[14px] leading-snug font-medium sm:text-[15px]">
                    {work.title}
                  </span>
                  {work.year !== null && <span className="text-[13px] text-fg-subtle">{work.year}</span>}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
