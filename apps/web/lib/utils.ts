import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Инициалы для аватара: первые буквы первых двух слов имени («Ivan Smirnov» → «IS»). */
export function initials(name: string): string {
  const words = name
    .split(/[\s.]+/)
    .map((word) => word.trim())
    .filter((word) => /[\p{L}]/u.test(word));
  return words
    .slice(0, 2)
    .map((word) => [...word][0]!.toUpperCase())
    .join("");
}

/** Числа в русской записи: 2140 → «2 140» (неразрывный пробел между группами). */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat("ru-RU").format(value).replace(/\s/g, "\u00A0");
}

/** Русские формы множественного числа: pluralize(5, "вуз", "вуза", "вузов"). */
export function pluralize(count: number, one: string, few: string, many: string): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

/** Косинусная близость 0..1 → «NN%». Округление, без перескалирования;
 * после SFR-4 живёт в tooltip бейджа и блоке «совпадение» профиля. */
export function matchPercent(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/** Словесный грейд на бейдже (SPEC_SFR4 §0.9): границы шкалы задаёт API
 * (score_weak/score_high в /health), фронт только называет грейд словами. */
export const GRADE_LABELS = {
  high: "высокое совпадение",
  medium: "среднее совпадение",
  low: "слабое совпадение",
} as const;

export function gradeLabel(grade: keyof typeof GRADE_LABELS): string {
  return GRADE_LABELS[grade];
}

const INSTITUTION_SHORT: Record<string, string> = {
  "Московский физико-технический институт": "МФТИ",
  "Московский государственный университет": "МГУ",
};

/** Короткое имя вуза для карточек («МФТИ»); незнакомый вуз остаётся полным. */
export function institutionShort(institution: string | null): string | null {
  if (!institution) return null;
  return INSTITUTION_SHORT[institution] ?? institution;
}

/** «МФТИ · профессор» — сегменты только из имеющихся данных (position пока null у всех). */
export function affiliationLine(institution: string | null, position: string | null): string {
  return [institutionShort(institution), position].filter(Boolean).join(" · ");
}
