"use client";

import { Pencil, Search } from "lucide-react";
import { useState } from "react";

import { SearchBox } from "@/components/search-box";

/** Строка текущего запроса: виден и редактируем (клик — разворачивает SearchBox). */
export function QueryBar({
  query,
  onSubmitQuery,
  startEditing = false,
}: {
  query: string;
  onSubmitQuery: (query: string) => void;
  startEditing?: boolean;
}) {
  const [editing, setEditing] = useState(startEditing);

  if (editing) {
    return (
      <SearchBox
        initialQuery={query}
        autoFocus
        onSubmitQuery={(next) => {
          setEditing(false);
          onSubmitQuery(next);
        }}
      />
    );
  }
  return (
    <div className="flex items-center gap-2.5 rounded-card border border-border bg-surface px-3.5 py-2.5 sm:gap-3 sm:px-[18px] sm:py-3.5">
      <Search className="size-[18px] shrink-0 text-fg-subtle" aria-hidden strokeWidth={2} />
      <p className="grow truncate text-[15px] leading-[1.4]">{query}</p>
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="flex min-h-11 shrink-0 cursor-pointer items-center gap-1.5 rounded-btn px-2 text-[14px] font-medium text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-accent"
      >
        <Pencil className="size-4 sm:hidden" aria-hidden strokeWidth={2} />
        {/* Один носитель подписи: на мобайле она sr-only при иконке, на десктопе
            видима. Второй sr-only span скринридер читал дважды. */}
        <span className="sr-only sm:not-sr-only">Изменить запрос</span>
      </button>
    </div>
  );
}
