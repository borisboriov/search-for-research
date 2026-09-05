"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { EmptyResults, ErrorState, QueryHint } from "@/components/empty-results";
import { DEFAULT_FILTERS, FiltersRow, FiltersSheetRow, type FilterState } from "@/components/filters";
import { QueryBar } from "@/components/query-bar";
import { validateQuery } from "@/components/search-box";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { SupervisorCardSkeleton, SupervisorResultCard } from "@/components/supervisor-card";
import type { MatchResponse } from "@/lib/types";
import { institutionShort, pluralize } from "@/lib/utils";

type State =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "invalid"; message: string }
  | { kind: "done"; response: MatchResponse };

async function fetchMatch(text: string): Promise<State> {
  // Границы те же, что у бэкенда: ручной ?q=ab — подсказка про запрос,
  // а не поход в API и не ложное «Сервис недоступен» (REVIEW_SFR3 Medium).
  const invalid = validateQuery(text);
  if (invalid) return { kind: "invalid", message: invalid };
  try {
    const response = await fetch("/api/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text, k: 10 }),
    });
    if (response.status === 422) {
      const payload: unknown = await response.json().catch(() => null);
      const detail =
        payload !== null && typeof payload === "object" && "detail" in payload
          ? payload.detail
          : null;
      return {
        kind: "invalid",
        message:
          typeof detail === "string"
            ? detail
            : "Запрос не прошёл проверку — попробуй переформулировать.",
      };
    }
    if (!response.ok) return { kind: "error" };
    return { kind: "done", response: (await response.json()) as MatchResponse };
  } catch {
    return { kind: "error" };
  }
}

function counterText(found: number, universities: number): string {
  return `Найдено ${found} ${pluralize(found, "научрук", "научрука", "научруков")} · ${universities} ${pluralize(universities, "вуз", "вуза", "вузов")}`;
}

function ResultsContent() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params.get("q")?.trim() ?? "";

  useEffect(() => {
    if (query === "") router.replace("/");
  }, [query, router]);

  if (query === "") return null;
  // key: смена запроса пересоздаёт состояние (сбрасывает фильтры и результаты)
  return <ResultsForQuery key={query} query={query} />;
}

function ResultsForQuery({ query }: { query: string }) {
  const router = useRouter();
  // Запрос уходит сразу при маунте, поэтому стартовое состояние — loading.
  const [state, setState] = useState<State>({ kind: "loading" });
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [editingQuery, setEditingQuery] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchMatch(query).then((next) => {
      if (!cancelled) setState(next);
    });
    return () => {
      cancelled = true;
    };
  }, [query]);

  const retry = useCallback(() => {
    setState({ kind: "loading" });
    fetchMatch(query).then(setState);
  }, [query]);

  const submitQuery = useCallback(
    (next: string) => {
      setEditingQuery(false);
      if (next === query) {
        setState({ kind: "loading" });
        fetchMatch(query).then(setState);
        return;
      }
      router.push(`/results?q=${encodeURIComponent(next)}`);
    },
    [query, router],
  );

  const results = useMemo(
    () => (state.kind === "done" ? state.response.results : []),
    [state],
  );
  const institutions = useMemo(
    () =>
      [...new Set(results.map((result) => institutionShort(result.institution)))].filter(
        (name): name is string => name !== null,
      ),
    [results],
  );
  const visible = useMemo(() => {
    const filtered = results.filter(
      (result) =>
        (filters.institution === "" ||
          institutionShort(result.institution) === filters.institution) &&
        (result.h_index ?? 0) >= filters.minHIndex,
    );
    if (filters.sort === "h_index") {
      return [...filtered].sort((a, b) => (b.h_index ?? 0) - (a.h_index ?? 0));
    }
    return filtered; // API уже отдаёт по убыванию score
  }, [results, filters]);
  const universities = new Set(visible.map((result) => result.institution)).size;
  const counter = counterText(visible.length, universities);

  return (
    <>
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-[1312px] grow flex-col gap-3.5 px-5 pt-5 pb-10 sm:gap-5 sm:px-16 sm:pt-9 sm:pb-14">
        <h1 className="sr-only">Результаты подбора научных руководителей</h1>
        <QueryBar
          key={String(editingQuery)}
          query={query}
          startEditing={editingQuery}
          onSubmitQuery={submitQuery}
        />

        {state.kind === "loading" && (
          <div aria-live="polite" className="flex flex-col gap-3.5">
            <p className="sr-only">Подбираем научруков…</p>
            {Array.from({ length: 5 }, (_, index) => (
              <SupervisorCardSkeleton key={index} />
            ))}
          </div>
        )}

        {state.kind === "error" && <ErrorState onRetry={retry} />}

        {state.kind === "invalid" && (
          <QueryHint message={state.message} onEditQuery={() => setEditingQuery(true)} />
        )}

        {state.kind === "done" && state.response.below_threshold && (
          <EmptyResults onEditQuery={() => setEditingQuery(true)} onExample={submitQuery} />
        )}

        {state.kind === "done" && !state.response.below_threshold && (
          <>
            <FiltersRow
              filters={filters}
              institutions={institutions}
              counter={counter}
              onChange={setFilters}
            />
            <FiltersSheetRow
              filters={filters}
              institutions={institutions}
              counter={counter}
              onChange={setFilters}
            />
            {/* Один reveal всего списка (fade + 8px, 200 мс) — других анимаций нет */}
            <div key={state.response.index_version + query} className="animate-reveal flex flex-col gap-3.5">
              {visible.map((result) => (
                <SupervisorResultCard key={result.author_id} result={result} query={query} />
              ))}
              {visible.length === 0 && (
                <p className="py-8 text-center text-[15px] text-fg-muted">
                  Под выбранные фильтры никто не попал — ослабь их или сбрось.
                </p>
              )}
            </div>
            <p className="flex flex-wrap justify-center gap-1.5 pt-2.5 text-center text-[12px] text-fg-subtle sm:text-[13px]">
              Наукометрия — по данным открытого каталога OpenAlex.
            </p>
          </>
        )}
      </main>
      <SiteFooter />
    </>
  );
}

export default function ResultsPage() {
  return (
    <Suspense>
      <ResultsContent />
    </Suspense>
  );
}
