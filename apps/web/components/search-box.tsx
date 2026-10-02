"use client";

import { ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn, pluralize } from "@/lib/utils";

export const QUERY_MIN = 3;
export const QUERY_MAX = 500;

export const QUERY_PLACEHOLDER =
  "Например: применение графовых нейросетей к предсказанию свойств молекул, хочу совмещать ML и химию…";

/** Ограничение интерфейса; параметры API этим компонентом не меняются. */
export function validateQuery(raw: string): string | null {
  const query = raw.trim();
  const length = Array.from(raw).length;
  if (length > QUERY_MAX) {
    const excess = length - QUERY_MAX;
    return `Убери ${excess} ${pluralize(excess, "символ", "символа", "символов")}: максимум ${QUERY_MAX}.`;
  }
  if (Array.from(query).length < QUERY_MIN) {
    return "Опиши интересы хотя бы парой слов — от 3 символов.";
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
  const formRef = useRef<HTMLFormElement>(null);
  const length = Array.from(value).length;
  const overLimit = length > QUERY_MAX;
  const visibleError = overLimit ? validateQuery(value) : error;

  useEffect(() => {
    const textarea = formRef.current?.querySelector("textarea");
    if (!textarea) return;
    // CSS ограничивает высоту, после неё длинный текст прокручивается внутри поля.
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [value]);

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
      ref={formRef}
      onSubmit={submit}
      className="flex w-full flex-col gap-3 rounded-search border border-border bg-surface p-3 sm:p-4"
    >
      <label className="sr-only" htmlFor="query">
        Описание научных интересов
      </label>
      <Textarea
        id="query"
        name="query"
        rows={3}
        autoFocus={autoFocus}
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
        aria-invalid={visibleError !== null}
        aria-describedby={`query-hint query-count${visibleError ? " query-error" : ""}`}
        className="min-h-24 max-h-[min(40dvh,320px)] overflow-y-auto px-1.5 py-2 text-[16px] sm:text-[17px]"
      />
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 text-[13px] text-fg-subtle">
        <p id="query-hint">Укажи тему, методы или объект исследования.</p>
        <span id="query-count" className={cn("shrink-0", overLimit && "text-danger")}>
          {length} / {QUERY_MAX}
        </span>
      </div>
      {visibleError && (
        <p id="query-error" role="alert" className="text-[14px] text-danger">
          {visibleError}
        </p>
      )}
      <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3")}>
        <span className="text-[13px] text-fg-subtle">Бесплатно · без регистрации</span>
        <Button type="submit" disabled={overLimit} className="max-sm:w-full">
          Подобрать научрука
          <ArrowRight className="size-4" aria-hidden strokeWidth={2} />
        </Button>
      </div>
    </form>
  );
}
