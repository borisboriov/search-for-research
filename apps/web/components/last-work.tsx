"use client";

import { useState } from "react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { TopWork } from "@/lib/types";
import { truncateTitle } from "@/lib/utils";

/**
 * «<год> · <название последней работы>» с обрезкой ~64 знаков и раскрытием
 * (P-15): живые английские заголовки OpenAlex вытягивали карточку в три
 * строки мелкого текста (наблюдение 3 baseline 11.09). Короткое название
 * показывается целиком — тогда ни обрезки, ни ссылки нет.
 *
 * `relative z-10` на кнопке: на мобайле и в превью лендинга вся карточка —
 * растянутая ссылка, и без подъёма кнопка оказалась бы под ней.
 */
export function LastWork({ work }: { work: TopWork }) {
  const [open, setOpen] = useState(false);
  const short = truncateTitle(work.title);
  const year = work.year === null ? null : String(work.year);
  return (
    <div className="text-[13.5px] leading-[1.45] text-fg-muted">
      {year !== null && <span className="text-fg-subtle">{year} · </span>}
      {short === work.title ? (
        work.title
      ) : (
        <Collapsible open={open} onOpenChange={setOpen} asChild>
          <span>
            {!open && <span>{short} </span>}
            <CollapsibleContent asChild>
              <span>{work.title} </span>
            </CollapsibleContent>
            <CollapsibleTrigger className="relative z-10 cursor-pointer text-[13px] text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-accent">
              {open ? "свернуть" : "раскрыть"}
            </CollapsibleTrigger>
          </span>
        </Collapsible>
      )}
    </div>
  );
}
