import { Info } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { SupervisorCard } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

function Metric({ value, label }: { value: number | null; label: string }) {
  if (value === null) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-display text-[24px] font-semibold text-accent sm:text-[28px]">
        {formatNumber(value)}
      </span>
      <span className="text-[13px] text-fg-muted">{label}</span>
    </div>
  );
}

export function MetricsCard({ card }: { card: SupervisorCard }) {
  return (
    <Card className="flex flex-col gap-[18px] p-[18px] sm:p-[22px]">
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-semibold sm:text-[16px]">Наукометрия</h2>
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger className="flex cursor-help items-center gap-1.5 text-[12px] text-fg-subtle">
              <Info className="size-3.5" aria-hidden strokeWidth={2} />
              по данным OpenAlex
            </TooltipTrigger>
            <TooltipContent>
              Открытый каталог научных публикаций OpenAlex (CC0). Цифры могут отставать от
              «свежих» профилей на других площадках.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Metric value={card.h_index} label="h-index" />
        <Metric value={card.works_count} label="публикаций" />
        <Metric value={card.cited_by_count} label="цитирований" />
      </div>
    </Card>
  );
}
