"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { buildLetter } from "@/lib/letter";
import type { SupervisorCard } from "@/lib/types";

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

function useCopy(): [boolean, (text: string) => void] {
  const [copied, setCopied] = useState(false);
  function copy(text: string) {
    const done = () => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(done)
        .catch(() => {
          if (legacyCopy(text)) done();
        });
    } else if (legacyCopy(text)) {
      done();
    }
  }
  return [copied, copy];
}

/** PoC контакта: email (если есть в данных) + шаблон письма + «Скопировать».
 * Отправка из сервиса — пилот (БФТ 2.2), здесь только copy-paste. */
export function ContactCard({ card }: { card: SupervisorCard }) {
  const letter = buildLetter(card);
  const [emailCopied, copyEmail] = useCopy();
  const [letterCopied, copyLetter] = useCopy();

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
      <div className="flex flex-col gap-2 rounded-btn border border-border bg-bg px-3.5 py-3">
        <p className="text-[12px] font-medium tracking-[0.06em] text-fg-subtle uppercase">
          Шаблон письма
        </p>
        <p className="text-[14px] leading-normal whitespace-pre-line text-fg-muted">{letter}</p>
      </div>
      <Button type="button" size="compact" className="w-full" onClick={() => copyLetter(letter)}>
        {letterCopied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
        {letterCopied ? "Скопировано" : "Скопировать письмо"}
      </Button>
      <p className="text-[12px] leading-normal text-fg-subtle">
        На этапе теста письмо отправляешь сам из своей почты. Отправка из сервиса и статусы
        заявок — скоро.
      </p>
    </Card>
  );
}
