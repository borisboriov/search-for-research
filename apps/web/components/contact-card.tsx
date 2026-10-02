"use client";

import { emitEvent } from "@/lib/analytics";
import { Check, Copy } from "lucide-react";
import { useId, useState } from "react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { buildLetter } from "@/lib/letter";
import type { SupervisorCard } from "@/lib/types";
import { worksByYear } from "@/lib/works";

// Фолбэк для сред без Clipboard API (например, http без TLS — REVIEW_SFR3 Low:
// кнопка молча не работала): скрытая textarea + execCommand("copy").
function legacyCopy(text: string): boolean {
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    area.remove();
  }
}

function useCopy(kind: "letter" | "address", author: string): [boolean, (text: string) => void] {
  const [copied, setCopied] = useState(false);
  async function copy(text: string) {
    let success = false;
    try {
      if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); success = true; }
      else success = legacyCopy(text);
    } catch { success = legacyCopy(text); }
    emitEvent(kind === "letter" ? (success ? "letter_copy_success" : "letter_copy_failed") : (success ? "address_copy_success" : "address_copy_failed"), { author_id: author });
    setCopied(success);
    if (success) setTimeout(() => setCopied(false), 2000);
  }

  return [copied, copy];
}

/** Черновик первого письма: студент выбирает работу и отдельно подтверждает её упоминание. */
export function ContactCard({ card }: { card: SupervisorCard }) {
  return <ContactDraft key={card.author_id} card={card} />;
}

function ContactDraft({ card }: { card: SupervisorCard }) {
  const works = worksByYear(card.top_works);
  const [selectedIndex, setSelectedIndex] = useState(works.length ? "0" : "");
  const [includeWork, setIncludeWork] = useState(false);
  const selectedWork = selectedIndex === "" ? null : works[Number(selectedIndex)] ?? null;
  const letter = buildLetter(card, includeWork ? selectedWork : null);
  const selectId = useId();
  const hintId = useId();
  const [emailCopied, copyEmail] = useCopy("address", card.author_id);
  const [letterCopied, copyLetter] = useCopy("letter", card.author_id);

  return (
    <Card className="flex flex-col gap-3.5 p-[18px] sm:p-[22px]">
      <h2 className="text-[16px] font-semibold">Написать научруку</h2>
      {card.email ? (
        <div className="flex items-center justify-between gap-2.5 rounded-btn border border-border bg-bg px-3.5 py-[11px]">
          <span className="truncate text-[14px]">{card.email}</span>
          <button
            type="button"
            onClick={() => copyEmail(card.email!)}
            className="flex shrink-0 cursor-pointer items-center gap-1 text-[13px] font-medium text-accent hover:text-accent-hover"
          >
            {emailCopied ? <Check className="size-3.5" aria-hidden /> : null}
            {emailCopied ? "Скопировано" : "Скопировать"}
          </button>
        </div>
      ) : (
        <p className="rounded-btn border border-border bg-bg px-3.5 py-[11px] text-[14px] text-fg-muted">
          Email не найден в открытых источниках — поищи на странице вуза или в последних статьях.
        </p>
      )}
      {works.length > 0 ? (
        <div className="flex min-w-0 flex-col gap-2">
          <label htmlFor={selectId} className="text-[14px] font-medium">Работа для письма</label>
          <select
            id={selectId}
            value={selectedIndex}
            aria-describedby={hintId}
            onChange={(event) => {
              emitEvent("work_selected", { author_id: card.author_id, ...(event.target.value !== "" ? { work_position: Number(event.target.value) } : {}) });
              setSelectedIndex(event.target.value);
              setIncludeWork(false);
            }}
            className="min-h-11 w-full min-w-0 rounded-btn border border-border bg-bg px-2 text-[14px] focus-visible:outline-2 focus-visible:outline-accent"
          >
            <option value="">Без упоминания работы</option>
            {works.map((work, index) => (
              <option key={`${work.title}-${work.year}-${index}`} value={String(index)}>
                {work.year ?? "год не указан"} · {work.title}
              </option>
            ))}
          </select>
          <p id={hintId} className="text-[12px] leading-normal text-fg-subtle">
            {works[0]?.year !== null
              ? "Предложена самая свежая из выбранных работ профиля."
              : "Годы работ неизвестны — выбери подходящую по названию."}
            {" "}Упомяни её, только если прочитал(а) и видишь связь со своей задачей.
          </p>
          {selectedWork && (
            <label className="flex cursor-pointer items-start gap-2 text-[13px] leading-normal text-fg-muted">
              <input
                type="checkbox"
                checked={includeWork}
                onChange={(event) => {
                  emitEvent("work_confirmed", { author_id: card.author_id, work_position: Number(selectedIndex), included: event.target.checked });
                  setIncludeWork(event.target.checked);
                }}
                className="mt-0.5 size-4 shrink-0 accent-accent"
              />
              Добавить выбранную работу в письмо
            </label>
          )}
        </div>
      ) : (
        <p className="text-[13px] leading-normal text-fg-muted">
          В профиле нет выбранных работ. Черновик подготовлен без упоминания публикации.
        </p>
      )}
      <div className="flex flex-col gap-2 rounded-btn border border-border bg-bg px-3.5 py-3">
        <p className="text-[12px] font-medium tracking-[0.06em] text-fg-subtle uppercase">
          Шаблон письма
        </p>
        <p aria-label="Черновик письма" className="text-[14px] leading-normal whitespace-pre-line text-fg-muted">{letter}</p>
      </div>
      <Button type="button" size="compact" className="w-full" onClick={() => copyLetter(letter)}>
        {letterCopied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
        {letterCopied ? "Скопировано" : "Скопировать письмо"}
      </Button>
      <p className="text-[12px] leading-normal text-fg-subtle">
        Замени поля в квадратных скобках своими данными и отправь письмо из своей почты.
        Копирование сохраняет черновик и не отправляет письмо научруку.
      </p>
    </Card>
  );
}
