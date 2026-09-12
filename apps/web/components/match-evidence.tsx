import type { MatchResult } from "@/lib/types";
import { cn, pluralize } from "@/lib/utils";

/**
 * Строка «почему подошёл» (P-18, Consensus): полоса из M сегментов, N из них
 * залиты, подпись со знаменателем и строка «K публикаций по теме с <год>».
 *
 * Рендерится **только** когда `/match` отдал все три поля — `matched_topics`,
 * `query_topics`, `works_on_topic`. Их даёт итерация ранжирования (SFR-7);
 * до неё блок скрыт, и карточка без него валидна. Ничего не вычисляем на
 * фронте и не подменяем косинусом (DESIGN_SYSTEM v2 §4).
 */
export function MatchEvidence({ result }: { result: MatchResult }) {
  const matched = result.matched_topics;
  const asked = result.query_topics;
  const works = result.works_on_topic;
  if (!matched || !asked || !works || asked.length === 0) return null;

  const total = asked.length;
  const hit = Math.min(matched.length, total);
  const since = works.since_year;

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-col gap-1.5">
        <div className="flex gap-1" aria-hidden>
          {Array.from({ length: total }, (_, index) => (
            <span
              key={index}
              className={cn(
                "h-1.5 flex-1 rounded-[3px]",
                index < hit
                  ? result.serendipity
                    ? "bg-serendipity"
                    : "bg-accent"
                  : "bg-border",
              )}
            />
          ))}
        </div>
        <p className="text-[12.5px] text-fg-subtle">
          Совпало {hit} из {total} {pluralize(total, "темы", "тем", "тем")} запроса · по
          публикациям OpenAlex
        </p>
      </div>
      <p className="text-[14px] leading-[1.45] text-fg-muted">
        {works.count} {pluralize(works.count, "публикация", "публикации", "публикаций")} по теме
        {since === null ? "" : ` с ${since}`}
      </p>
    </div>
  );
}
