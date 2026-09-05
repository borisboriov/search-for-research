"use client";

import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/logo";

/**
 * Глобальный error boundary: сюда прилетают исключения серверного рендера —
 * прежде всего упавший API на странице НР (lib/api.ts бросает на сеть/5xx).
 * Ответ 500 не кэшируется ISR, поэтому после восстановления API страница
 * оживает первым же запросом, без ожидания часа (REVIEW_SFR3 High №1).
 */
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto flex min-h-[60vh] w-full max-w-[640px] flex-col items-center justify-center gap-[18px] px-5 py-16 text-center">
      <span className="flex size-16 items-center justify-center rounded-full bg-accent-soft">
        <LogoMark className="size-[30px] text-fg-subtle" />
      </span>
      <h1 className="font-display text-[24px] font-semibold sm:text-[28px]">
        Сервис сейчас недоступен
      </h1>
      <p className="text-[15px] leading-relaxed text-fg-muted sm:text-[16px]">
        Не получилось загрузить данные. Попробуй ещё раз через минуту.
      </p>
      <Button type="button" onClick={reset} className="mt-1.5">
        Повторить
      </Button>
    </main>
  );
}
