import { Info } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { SupervisorCard } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

// Цифры — цветом `--fg`, не акцентом: правило 2 направления B (заливок и
// акцентных пятен на экран — две, и числа не из их числа).
function Metric({ value, label }: { value: number | null; label: string }) {
  if (value === null) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className="font-display text-[24px] leading-none font-semibold tracking-[-0.01em] sm:text-[28px]">
        {formatNumber(value)}
      </span>
      <span className="text-[13px] text-fg-muted">{label}</span>
    </div>
  );
}

/**
 * Наукометрия профиля. Над цифрами — плашка происхождения данных (P-08,
 * ПроДокторов): раньше это была мелкая подпись у заголовка. Дата — дата данных
 * каталога из `/health` (`data_updated_at`, #16; у индекса без штампа —
 * `built_at`); ответа нет — плашка без даты.
 * Она же несёт tooltip «по данным OpenAlex».
 */
export function MetricsCard({ card, updatedAt }: { card: SupervisorCard; updatedAt: string | null }) {
  return (
    <Card className="flex flex-col gap-4 p-[18px] sm:p-[22px]">
      <h2 className="text-[16px] font-semibold">Наукометрия</h2>
      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger className="flex w-full cursor-help items-center gap-2 rounded-btn bg-bg-muted px-3 py-2 text-left text-[12.5px] text-fg-muted">
            <Info className="size-3.5 shrink-0 text-fg-subtle" aria-hidden strokeWidth={2} />
            Данные: OpenAlex{updatedAt === null ? "" : ` · обновлено ${updatedAt}`}
          </TooltipTrigger>
          <TooltipContent>
            Открытый каталог научных публикаций OpenAlex (CC0). Цифры могут отставать от
            «свежих» профилей на других площадках.
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <div className="grid grid-cols-3 gap-3">
        <Metric value={card.h_index} label="h-index" />
        <Metric value={card.works_count} label="публикаций" />
        <Metric value={card.cited_by_count} label="цитирований" />
      </div>
    </Card>
  );
}
