"use client";

import { ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export const QUERY_MIN = 3;
export const QUERY_MAX = 500;

export const QUERY_PLACEHOLDER =
  "Например: применение графовых нейросетей к предсказанию свойств молекул, хочу совмещать ML и химию…";

/** Валидация до похода в API: те же границы, что у бэкенда (3–500 символов). */
export function validateQuery(raw: string): string | null {
  const query = raw.trim();
  if (query.length < QUERY_MIN) {
    return "Опиши интересы хотя бы парой слов — от 3 символов.";
  }
  if (query.length > QUERY_MAX) {
    return `Слишком длинно: ${query.length} символов, максимум ${QUERY_MAX}. Оставь суть — тему и методы.`;
  }
  return null;
}

export function SearchBox({
  initialQuery = "",
  autoFocus = false,
  onSubmitQuery,
}: {
  initialQuery?: string;
  autoFocus?: boolean;
  /** Без обработчика сабмит уводит на /results?q=… (лендинг). */
  onSubmitQuery?: (query: string) => void;
}) {
  const router = useRouter();
  const [value, setValue] = useState(initialQuery);
  const [error, setError] = useState<string | null>(null);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const message = validateQuery(value);
    if (message) {
      setError(message);
      return;
    }
    const query = value.trim();
    if (onSubmitQuery) {
      onSubmitQuery(query);
    } else {
      router.push(`/results?q=${encodeURIComponent(query)}`);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="flex w-full flex-col gap-3.5 rounded-search border border-border bg-surface p-4 shadow-search sm:gap-4 sm:p-5"
    >
      <label className="sr-only" htmlFor="query">
        Описание научных интересов
      </label>
      <Textarea
        id="query"
        name="query"
        rows={3}
        autoFocus={autoFocus}
        maxLength={QUERY_MAX + 100}
        placeholder={QUERY_PLACEHOLDER}
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          if (error) setError(null);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.currentTarget.form?.requestSubmit();
          }
        }}
        aria-invalid={error !== null}
        aria-describedby={error ? "query-error" : undefined}
        className="min-h-[88px]"
      />
      {error && (
        <p id="query-error" role="alert" className="text-[14px] text-danger">
          {error}
        </p>
      )}
      <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4")}>
        <span className="text-[14px] text-fg-subtle">Бесплатно · без регистрации</span>
        <Button type="submit">
          Подобрать научрука
          <ArrowRight className="size-[18px]" aria-hidden strokeWidth={2} />
        </Button>
      </div>
    </form>
  );
}
