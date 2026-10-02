import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/logo";

// In-domain примеры из packages/sfr-match/eval/queries.jsonl (q01, q03, q13) —
// требование спеки: примеры реальные, не выдуманные (SPEC_SFR3 §2).
export const EXAMPLE_QUERIES = [
  "Хочу заниматься машинным обучением для анализа текстов, интересна тема депрессии в соцсетях. Есть кто-то, кто этим занимается?",
  "Интересна физика элементарных частиц, хочу поучаствовать в экспериментах на коллайдере",
  "Интересна рентгеновская дифракция и определение структуры кристаллов",
];

/** Состояние below_threshold: «уверенных совпадений нет» — подсказка, не тупик. */
export function EmptyResults({
  onEditQuery,
  onExample,
}: {
  onEditQuery: () => void;
  onExample: (query: string) => void;
}) {
  return (
    <Card className="mt-2 flex flex-col items-center gap-[18px] rounded-search px-5 py-10 sm:px-12 sm:py-14">
      <span className="flex size-16 items-center justify-center rounded-full bg-accent-soft">
        <svg
          viewBox="0 0 48 48"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.6}
          strokeDasharray="4 4"
          className="size-[30px] text-accent"
          aria-hidden
        >
          <circle cx="18" cy="24" r="12" />
          <circle cx="30" cy="24" r="12" />
        </svg>
      </span>
      <h2 className="text-center font-display text-[24px] font-semibold sm:text-[28px]">
        Уверенных совпадений нет
      </h2>
      <p className="max-w-[560px] text-center text-[15px] leading-relaxed text-fg-muted sm:text-[16px]">
        В текущем каталоге не нашлось уверенных совпадений с твоим запросом. Уточни тему,
        метод или объект исследования — или попробуй близкую область.
      </p>
      <div className="mt-1.5 flex w-full max-w-[620px] flex-col gap-2.5">
        <p className="text-[13px] font-medium tracking-[0.06em] text-fg-subtle uppercase">
          Примеры удачных запросов
        </p>
        {EXAMPLE_QUERIES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onExample(example)}
            className="cursor-pointer rounded-btn border border-border bg-bg px-4 py-3 text-left text-[15px] hover:border-accent-border focus-visible:outline-2 focus-visible:outline-accent"
          >
            {example}
          </button>
        ))}
      </div>
      <Button type="button" onClick={onEditQuery} className="mt-1.5">
        Изменить запрос
      </Button>
    </Card>
  );
}

/** Серая зона порога (confidence == "weak", SPEC_SFR4 §0.9): top-1 выше
 * «уверенных совпадений нет», но ниже минимума живых попаданий. Выдача
 * остаётся видимой — баннер над ней, а не пустое состояние. */
export function WeakBanner({ onEditQuery }: { onEditQuery?: () => void }) {
  return (
    <Card className="mt-2 flex items-start gap-3 rounded-search px-5 py-4 sm:items-center sm:gap-3.5 sm:px-7 sm:py-5">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent-soft">
        <svg
          viewBox="0 0 48 48"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.6}
          strokeDasharray="4 4"
          className="size-5 text-accent"
          aria-hidden
        >
          <circle cx="18" cy="24" r="12" />
          <circle cx="30" cy="24" r="12" />
        </svg>
      </span>
      <div className="min-w-0 text-[14px] leading-relaxed text-fg-muted sm:text-[15px]">
        <p>Совпадения слабые: запрос мало похож на описания исследователей в каталоге.</p>
        <p className="mt-1">Попробуй уточнить запрос:</p>
        <ul className="mt-1 list-disc pl-5">
          <li>Назови конкретную тему: например, анализ текстов вместо «машинное обучение».</li>
          <li>Добавь метод, который хочешь использовать: например, нейросети.</li>
          <li>Укажи объект исследования: например, тексты соцсетей.</li>
        </ul>
        {onEditQuery && (
          <Button type="button" variant="secondary" onClick={onEditQuery} className="mt-3">
            Изменить запрос
          </Button>
        )}
      </div>
    </Card>
  );
}

/** 422 или невалидный ?q= — подсказка про сам запрос, не «сервис недоступен»
 * (REVIEW_SFR3 Medium: ручной ?q=ab показывал ложную ошибку с вечным «Повторить»). */
export function QueryHint({
  message,
  onEditQuery,
}: {
  message: string;
  onEditQuery: () => void;
}) {
  return (
    <Card className="mt-2 flex flex-col items-center gap-[18px] rounded-search px-5 py-10 sm:px-12 sm:py-14">
      <span className="flex size-16 items-center justify-center rounded-full bg-accent-soft">
        <svg
          viewBox="0 0 48 48"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.6}
          className="size-[30px] text-accent"
          aria-hidden
        >
          <circle cx="22" cy="22" r="12" />
          <path d="M31 31 L40 40" strokeLinecap="round" />
        </svg>
      </span>
      <h2 className="text-center font-display text-[24px] font-semibold sm:text-[28px]">
        Поправь запрос
      </h2>
      <p className="max-w-[560px] text-center text-[15px] leading-relaxed text-fg-muted sm:text-[16px]">
        {message}
      </p>
      <Button type="button" onClick={onEditQuery} className="mt-1.5">
        Изменить запрос
      </Button>
    </Card>
  );
}

/** 429 — сработал лимит частоты запросов (#23). Сервис жив, студент просто
 * спрашивал подряд: сказать это прямо, иначе первый тестер пилота решит, что
 * сервис сломан. Тот же вид, что у ошибки, — отдельного макета нет. */
export function RateLimitedState({ onRetry }: { onRetry: () => void }) {
  return (
    <Card className="mt-2 flex flex-col items-center gap-[18px] rounded-search px-5 py-10 sm:px-12 sm:py-14">
      <span className="flex size-16 items-center justify-center rounded-full bg-accent-soft">
        <LogoMark className="size-[30px] text-fg-subtle" />
      </span>
      <h2 className="text-center font-display text-[24px] font-semibold sm:text-[28px]">
        Слишком много запросов подряд
      </h2>
      <p className="max-w-[560px] text-center text-[15px] leading-relaxed text-fg-muted sm:text-[16px]">
        Сервис работает — просто запросы пришли чаще, чем он успевает их разбирать.
        Подожди немного, около минуты, и попробуй ещё раз.
      </p>
      <Button type="button" onClick={onRetry} className="mt-1.5">
        Повторить
      </Button>
    </Card>
  );
}

/** Ошибка сети / API недоступен — в том же стиле (макета нет, SPEC_SFR3 §2). */
export function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <Card className="mt-2 flex flex-col items-center gap-[18px] rounded-search px-5 py-10 sm:px-12 sm:py-14">
      <span className="flex size-16 items-center justify-center rounded-full bg-accent-soft">
        <LogoMark className="size-[30px] text-fg-subtle" />
      </span>
      <h2 className="text-center font-display text-[24px] font-semibold sm:text-[28px]">
        Сервис сейчас недоступен
      </h2>
      <p className="max-w-[560px] text-center text-[15px] leading-relaxed text-fg-muted sm:text-[16px]">
        Не получилось связаться с сервером подбора. Попробуй ещё раз через минуту.
      </p>
      <Button type="button" onClick={onRetry} className="mt-1.5">
        Повторить
      </Button>
    </Card>
  );
}
