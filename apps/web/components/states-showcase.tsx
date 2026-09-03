"use client";

import { EmptyResults, ErrorState } from "@/components/empty-results";
import { SupervisorCardSkeleton, SupervisorResultCard } from "@/components/supervisor-card";
import type { MatchResult } from "@/lib/types";

// Образец для вёрстки (данные вымышленные — страница dev-only, в продукт не ведёт).
const SAMPLE: MatchResult = {
  author_id: "A0000000000",
  name: "Образец Карточки",
  institution: "Московский физико-технический институт",
  h_index: 15,
  works_count: 54,
  topics: ["Байесовские методы", "Материаловедение", "Оптимизация"],
  profile_text: "Образец Карточки — МФТИ.",
  cited_by_count: 420,
  position: null,
  email: null,
  top_works: [{ title: "Bayesian optimisation of alloy compositions", year: 2024 }],
  serendipity: false,
  score: 0.92,
  rank: 1,
};

export function StatesShowcase() {
  return (
    <main className="mx-auto flex w-full max-w-[1312px] flex-col gap-8 px-5 py-10 sm:px-16">
      <h1 className="font-display text-[28px] font-semibold">Состояния компонентов (dev)</h1>

      <section className="flex flex-col gap-3.5">
        <h2 className="text-[16px] font-semibold">Карточка: обычная</h2>
        <SupervisorResultCard result={SAMPLE} query="образец" />
      </section>

      <section className="flex flex-col gap-3.5">
        <h2 className="text-[16px] font-semibold">Карточка: serendipity</h2>
        <SupervisorResultCard
          result={{ ...SAMPLE, author_id: "A0000000001", serendipity: true }}
          query="образец"
        />
      </section>

      <section className="flex flex-col gap-3.5">
        <h2 className="text-[16px] font-semibold">Карточка: skeleton</h2>
        <SupervisorCardSkeleton />
      </section>

      <section className="flex flex-col gap-3.5">
        <h2 className="text-[16px] font-semibold">Пустое состояние</h2>
        <EmptyResults onEditQuery={() => {}} onExample={() => {}} />
      </section>

      <section className="flex flex-col gap-3.5">
        <h2 className="text-[16px] font-semibold">Ошибка сети</h2>
        <ErrorState onRetry={() => {}} />
      </section>
    </main>
  );
}
