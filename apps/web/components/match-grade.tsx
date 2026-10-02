"use client";

import { useSearchParams } from "next/navigation";

import { MatchBadge } from "@/components/match-badge";
import type { Grade } from "@/lib/types";

const GRADES: readonly string[] = ["high", "medium", "low"];

/**
 * Совпадение с запросом на странице НР — **словом**, тем же бейджем, что в
 * списке: крупный «43%» читался как школьная оценка и расходился с грейдом в
 * выдаче (решение 11.09, `docs/DECISIONS.md`). Численных оценок нет
 * и в раскрываемом объяснении бейджа.
 *
 * Грейд приходит в ссылке с результатов (`?grade=`), как и score: фронт его
 * не вычисляет — границы шкалы знает только API. Пришли на профиль напрямую —
 * блока нет. `?score=` остался проверкой происхождения ссылки (она пришла с
 * живой выдачи), на экран он не попадает.
 *
 * Клиентский островок: чтение searchParams в серверном компоненте сделало бы
 * страницу динамической и убило бы ISR (docs/DECISIONS.md).
 */
export function MatchGrade({ className }: { className?: string }) {
  const params = useSearchParams();
  const grade = params.get("grade");
  const raw = params.get("score");
  const score = raw === null ? NaN : Number(raw);
  if (!Number.isFinite(score) || score <= 0 || score > 1) return null;
  if (grade === "serendipity") {
    return <MatchBadge grade="low" serendipity className={className} />;
  }
  if (grade === null || !GRADES.includes(grade)) return null;
  return <MatchBadge grade={grade as Grade} className={className} />;
}
