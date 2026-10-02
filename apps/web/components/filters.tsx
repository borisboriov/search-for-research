"use client";

import { ChevronDown, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

export interface FilterState {
  institution: string; // "" = все
  minHIndex: number; // 0 = любой
  sort: "score" | "h_index";
}

export const DEFAULT_FILTERS: FilterState = { institution: "", minHIndex: 0, sort: "score" };

const H_INDEX_OPTIONS = [0, 10, 20, 50];

function Chip({
  label,
  value,
  active,
  children,
  onChange,
  className,
}: {
  label: string;
  value: string;
  active?: boolean;
  children: React.ReactNode;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <label
      className={cn(
        "relative flex min-h-11 min-w-0 max-w-full cursor-pointer items-center gap-1.5 rounded-full border px-3 py-2 text-[14px] focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent",
        active
          ? "border-accent-border bg-accent-soft font-medium text-accent"
          : "border-border bg-surface text-fg",
        className,
      )}
    >
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="absolute inset-0 w-full min-w-0 cursor-pointer appearance-none opacity-0"
        aria-label={label}
      >
        {children}
      </select>
      <span className="min-w-0 [overflow-wrap:anywhere]" aria-hidden>{label}</span>
      <ChevronDown className="size-3.5 shrink-0 text-fg-muted" aria-hidden strokeWidth={2} />
    </label>
  );
}

function FilterChips({
  filters,
  institutions,
  onChange,
}: {
  filters: FilterState;
  institutions: string[];
  onChange: (filters: FilterState) => void;
}) {
  return (
    <>
      <Chip
        label={`Организация: ${filters.institution || "все"}`}
        value={filters.institution}
        active={filters.institution !== ""}
        onChange={(institution) => onChange({ ...filters, institution })}
      >
        <option value="">все</option>
        {institutions.map((institution) => (
          <option key={institution} value={institution}>
            {institution}
          </option>
        ))}
      </Chip>
      <Chip
        label={`h-index: ${filters.minHIndex === 0 ? "любой" : `от ${filters.minHIndex}`}`}
        value={String(filters.minHIndex)}
        active={filters.minHIndex !== 0}
        onChange={(min) => onChange({ ...filters, minHIndex: Number(min) })}
      >
        {H_INDEX_OPTIONS.map((option) => (
          <option key={option} value={option}>
            {option === 0 ? "любой" : `от ${option}`}
          </option>
        ))}
      </Chip>
      {/* Чип «Должность» из макета скрыт: в данных каталога должности пока нет
          (position = null у всех) — фильтр по всегда-пустому полю только путает. */}
    </>
  );
}

function SortChip({
  filters,
  onChange,
}: {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
}) {
  return (
    <Chip
      label={filters.sort === "score" ? "По совпадению" : "По h-index"}
      value={filters.sort}
      active
      className="border-fg bg-fg font-medium text-bg [&_svg]:text-bg"
      onChange={(sort) => onChange({ ...filters, sort: sort as FilterState["sort"] })}
    >
      <option value="score">По совпадению</option>
      <option value="h_index">По h-index</option>
    </Chip>
  );
}

/** Десктоп: чипы в строку над списком, активная сортировка — справа.
 * Счётчик с v2 живёт не здесь, а заголовком над списком (DESIGN_SYSTEM §3). */
export function FiltersRow({
  filters,
  institutions,
  onChange,
}: {
  filters: FilterState;
  institutions: string[];
  onChange: (filters: FilterState) => void;
}) {
  return (
    <div className="hidden items-center justify-between gap-3 sm:flex">
      <div className="flex flex-wrap items-center gap-2">
        <FilterChips filters={filters} institutions={institutions} onChange={onChange} />
      </div>
      <SortChip filters={filters} onChange={onChange} />
    </div>
  );
}

/** Мобайл: кнопка «Фильтры», открывающая Sheet со всеми чипами. */
export function FiltersSheetRow({
  filters,
  institutions,
  onChange,
}: {
  filters: FilterState;
  institutions: string[];
  onChange: (filters: FilterState) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(filters);
  return (
    <div className="flex sm:hidden">
      <Sheet open={open} onOpenChange={(next) => {
        if (next) setDraft(filters);
        setOpen(next);
      }}>
        <SheetTrigger className="flex min-h-11 cursor-pointer items-center gap-2 rounded-btn border border-border bg-surface px-[18px] text-[15px] font-medium">
          <SlidersHorizontal className="size-4" aria-hidden strokeWidth={2} />
          Фильтры
        </SheetTrigger>
        <SheetContent title="Фильтры">
          <div className="flex min-w-0 flex-wrap gap-2.5">
            <FilterChips filters={draft} institutions={institutions} onChange={setDraft} />
            <SortChip filters={draft} onChange={setDraft} />
          </div>
          <div className="flex flex-wrap gap-2.5">
            <Button type="button" onClick={() => { onChange(draft); setOpen(false); }}>
              Применить
            </Button>
            <Button type="button" variant="secondary" onClick={() => setDraft(DEFAULT_FILTERS)}>
              Сбросить
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
