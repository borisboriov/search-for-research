"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  EmptyResults,
  ErrorState,
  QueryHint,
  RateLimitedState,
  WeakBanner,
} from "@/components/empty-results";
import { DEFAULT_FILTERS, FiltersRow, FiltersSheetRow, type FilterState } from "@/components/filters";
import { QueryBar } from "@/components/query-bar";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { SupervisorCardSkeleton, SupervisorResultCard } from "@/components/supervisor-card";
import { beginSearch, emitEvent, prepareSearch, whenVisible } from "@/lib/analytics";
import type { EventData } from "@/lib/analytics-contract";
import { fetchMatch, type State } from "@/lib/match";
import { counterText, institutionShort } from "@/lib/utils";


function ResultsContent() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params.get("q") ?? "";

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

  const [searchId, setSearchId] = useState<string | undefined>();
  const trace = useRef<{ visit: string; search: string; request: string } | null>(null);
  const startedAt = useRef(0);
  const initial = useRef<Promise<{ state: State; generation: number }> | null>(null);
  const generation = useRef(0);
  const displayed = useRef<string | null>(null);
  const run = useCallback(async (source?: EventData["source"]) => {
    const currentGeneration = ++generation.current;
    const nextTrace = await beginSearch(query, source);
    trace.current = nextTrace;
    setSearchId(nextTrace.search);
    startedAt.current = performance.now();
    return { state: await fetchMatch(query, nextTrace), generation: currentGeneration };
  }, [query]);
  useEffect(() => {
    let cancelled = false;
    initial.current ??= run();
    initial.current.then(next => { if (!cancelled && next.generation === generation.current) setState(next.state); });
    return () => { cancelled = true; };
  }, [run]);
  useEffect(() => {
    if (state.kind !== "done" || !trace.current) return;
    return whenVisible(() => {
      const context = trace.current!;
      if (displayed.current === context.search) return;
      displayed.current = context.search;
      const data = { confidence: state.response.confidence, elapsed_ms: Math.min(86400000, performance.now() - startedAt.current) };
      emitEvent(state.response.confidence === "none" ? "empty_shown" : "results_shown", data, context.search, context.request);
      if (state.response.confidence === "weak") emitEvent("weak_shown", data, context.search, context.request);
    });
  }, [state]);
  const retry = useCallback(() => {
    setState({ kind: "loading" });
    void run("repeat").then(next => { if (next.generation === generation.current) setState(next.state); });
  }, [run]);
  const submitQuery = useCallback((next: string) => {
    setEditingQuery(false);
    if (next === query) { retry(); return; }
    void prepareSearch(next, "reformulated").then(() => router.push(`/results?q=${encodeURIComponent(next)}`));
  }, [query, router, retry]);
  const applyFilters = useCallback((next: FilterState) => {
    if (next.institution !== filters.institution || next.minHIndex !== filters.minHIndex) emitEvent("filters_applied", { filters: { institution: next.institution ? [next.institution] : [], min_h_index: next.minHIndex }, filter_count: Number(Boolean(next.institution)) + Number(next.minHIndex > 0) }, trace.current?.search);
    if (next.sort !== filters.sort) emitEvent("sort_applied", { sort: next.sort === "h_index" ? "h_index" : "relevance" }, trace.current?.search);
    setFilters(next);
  }, [filters]);

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
  // Короткие имена + отсев null: иначе «2 организации» при одной (REVIEW_SFR3 Low)
  const organisations = new Set(
    visible.map((result) => institutionShort(result.institution)).filter(Boolean),
  ).size;
  const counter = counterText(visible.length, organisations);

  return (
    <>
      <SiteHeader />
      {/* Колонка 920px по центру (S-08): на 1440 карточка во всю ширину
          растягивала строку последней работы в одну линию мелкого текста. */}
      <main className="mx-auto flex w-full max-w-[920px] grow flex-col gap-4 px-4 pt-5 pb-10 sm:gap-5 sm:pt-8 sm:pb-16">
        <h1 className="sr-only">Результаты подбора научных руководителей</h1>
        <QueryBar
          key={String(editingQuery)}
          query={query}
          startEditing={editingQuery}
          onSubmitQuery={submitQuery}
        />

        {state.kind === "loading" && (
          <div aria-live="polite" className="flex flex-col gap-4">
            <p className="sr-only">Подбираем научруков…</p>
            {Array.from({ length: 5 }, (_, index) => (
              <SupervisorCardSkeleton key={index} />
            ))}
          </div>
        )}

        {state.kind === "error" && <ErrorState onRetry={retry} />}
        {state.kind === "rate_limited" && <RateLimitedState onRetry={retry} />}

        {state.kind === "invalid" && (
          <QueryHint message={state.message} onEditQuery={() => setEditingQuery(true)} />
        )}

        {state.kind === "done" && state.response.confidence === "none" && (
          <EmptyResults onEditQuery={() => setEditingQuery(true)} onExample={submitQuery} />
        )}

        {state.kind === "done" && state.response.confidence !== "none" && (
          <>
            {/* Серая зона: баннер над выдачей, сама выдача остаётся (§0.9) */}
            {state.response.confidence === "weak" && (
              <WeakBanner onEditQuery={() => setEditingQuery(true)} />
            )}
            <FiltersRow filters={filters} institutions={institutions} onChange={applyFilters} />
            <FiltersSheetRow filters={filters} institutions={institutions} onChange={applyFilters} />
            {/* Счётчик — заголовком, под ним подпись о порядке выдачи (S-09) */}
            <div className="flex flex-col gap-1 pt-1">
              <h2 className="font-display text-[22px] leading-[1.2] font-semibold sm:text-[30px]">
                {counter}
              </h2>
              {/* Подпись про порядок выдачи бессмысленна над пустым списком */}
              {visible.length > 0 && (
                <p className="text-[13.5px] text-fg-subtle">
                  {filters.sort === "h_index"
                    ? "Отсортировано по h-index"
                    : "Отсортировано по совпадению с запросом"}
                  {" · темы и работы — по публикациям OpenAlex"}
                </p>
              )}
            </div>
            {/* Один reveal всего списка (fade + 8px, 200 мс) — других анимаций нет */}
            <div key={state.response.index_version + query} className="animate-reveal flex flex-col gap-4">
              {visible.map((result, position) => (
                <SupervisorResultCard key={result.author_id} result={result} query={query} searchId={searchId} position={position + 1} />
              ))}
              {/* Сам факт «никто не попал» теперь в заголовке — здесь остаётся
                  только действие, чтобы не повторять одну мысль дважды. */}
              {visible.length === 0 && (
                <p className="py-8 text-center text-[15px] text-fg-muted">
                  Ослабь фильтры или сбрось их.
                </p>
              )}
            </div>
            <p className="flex flex-wrap justify-center gap-1.5 pt-2 text-center text-[13px] text-fg-subtle">
              Наукометрия — по данным открытого каталога OpenAlex.
              <Link href="/#how-it-works" className="text-accent hover:text-accent-hover">
                Как работает подбор
              </Link>
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
