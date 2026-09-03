"use client";

import { ChevronDown, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

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
        "relative flex min-h-11 cursor-pointer items-center gap-2 rounded-full border px-3.5 text-[14px] font-medium whitespace-nowrap",
        active
          ? "border-accent-border bg-accent-soft text-accent"
          : "border-border bg-surface text-fg",
        className,
      )}
    >
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="absolute inset-0 cursor-pointer appearance-none opacity-0"
        aria-label={label}
      >
        {children}
      </select>
      <span aria-hidden>{label}</span>
      <ChevronDown className="size-3.5 text-fg-muted" aria-hidden strokeWidth={2} />
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
        label={`Вуз: ${filters.institution || "все"}`}
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
      onChange={(sort) => onChange({ ...filters, sort: sort as FilterState["sort"] })}
    >
      <option value="score">По совпадению</option>
      <option value="h_index">По h-index</option>
    </Chip>
  );
}

/** Десктоп: чипы в строку над списком; счётчик и сортировка справа. */
export function FiltersRow({
  filters,
  institutions,
  counter,
  onChange,
}: {
  filters: FilterState;
  institutions: string[];
  counter: string;
  onChange: (filters: FilterState) => void;
}) {
  return (
    <div className="hidden items-center justify-between gap-4 sm:flex">
      <div className="flex items-center gap-2.5">
        <FilterChips filters={filters} institutions={institutions} onChange={onChange} />
      </div>
      <div className="flex items-center gap-4">
        <p className="text-[14px] text-fg-muted">{counter}</p>
        <SortChip filters={filters} onChange={onChange} />
      </div>
    </div>
  );
}

/** Мобайл: счётчик + кнопка «Фильтры», открывающая Sheet. */
export function FiltersSheetRow({
  filters,
  institutions,
  counter,
  onChange,
}: {
  filters: FilterState;
  institutions: string[];
  counter: string;
  onChange: (filters: FilterState) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex items-center justify-between gap-2.5 sm:hidden">
      <p className="text-[13px] text-fg-muted">{counter}</p>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger className="flex min-h-11 cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3.5 text-[14px] font-medium">
          <SlidersHorizontal className="size-4" aria-hidden strokeWidth={2} />
          Фильтры
        </SheetTrigger>
        <SheetContent title="Фильтры">
          <div className="flex flex-wrap gap-2.5">
            <FilterChips filters={filters} institutions={institutions} onChange={onChange} />
            <SortChip filters={filters} onChange={onChange} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
