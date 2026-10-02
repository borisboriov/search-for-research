import type { TopWork } from "@/lib/types";

/** Только порядок отображения уже отобранных API работ; исходный массив не меняется. */
export function worksByYear(works: readonly TopWork[]): TopWork[] {
  return [...works].sort((a, b) => {
    if (a.year === b.year) return 0;
    if (a.year === null) return 1;
    if (b.year === null) return -1;
    return b.year - a.year;
  });
}
