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

/** Название последней работы в карточке обрезается ~64 знаками и раскрывается
 * ссылкой «раскрыть» (P-15): живые английские заголовки OpenAlex вытягивали
 * карточку в три строки мелкого текста (наблюдение 3 baseline 11.09).
 * Режем по границе слова, чтобы не рвать слово посередине. */
export const TITLE_LIMIT = 64;

export function truncateTitle(title: string, limit: number = TITLE_LIMIT): string {
  if (title.length <= limit) return title;
  const head = title.slice(0, limit);
  const space = head.lastIndexOf(" ");
  return `${(space > limit * 0.6 ? head.slice(0, space) : head).trimEnd()}…`;
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

/** Какую дату показывать в плашке P-08 «обновлено»: дату данных каталога
 * (`data_updated_at`, #16), а если индекс без штампа — дату его сборки. */
export function catalogueDate(
  health: { built_at?: string | null; data_updated_at?: string | null } | null | undefined,
): string | null {
  return health?.data_updated_at || health?.built_at || null;
}

/** Дата из `/health` (`data_updated_at` или `built_at`, ISO) для плашки P-08.
 * Считаем в UTC, чтобы дата не «плыла» от часового пояса рендерящей машины;
 * мусор на входе — null, плашка тогда показывается без даты. */
export function formatIndexDate(builtAt: string | null | undefined): string | null {
  if (!builtAt) return null;
  const date = new Date(builtAt);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

/** Счётчик выдачи заголовком (DESIGN_SYSTEM v2 §3, S-09). «Вуз» → «Организация»:
 * научрук может работать в НИИ, а в OpenAlex это такие же `institutions`
 * (docs/DECISIONS.md 12.09). Число организаций считается по самой выдаче. */
export function counterText(found: number, organisations: number): string {
  // Счётчик считается по отфильтрованной выдаче, и при жёстком фильтре
  // заголовок говорил «Нашли 0 научруков из 0 организаций» — формально верно,
  // но читается как «сервис ничего не нашёл по запросу» (REVIEW_SFR-6).
  if (found === 0) return "Под фильтры никто не попал";
  const people = `${found} ${pluralize(found, "научрука", "научрука", "научруков")}`;
  const orgs = `${organisations} ${pluralize(organisations, "организации", "организаций", "организаций")}`;
  return `Нашли ${people} из ${orgs}`;
}

/** «МФТИ · профессор» — сегменты только из имеющихся данных (position пока null у всех). */
export function affiliationLine(institution: string | null, position: string | null): string {
  return [institutionShort(institution), position].filter(Boolean).join(" · ");
}
