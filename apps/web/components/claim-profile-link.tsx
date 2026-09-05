import { UserRound } from "lucide-react";

import { claimProfileMailto } from "@/lib/letter";

/** «Это вы?» — юр. контур: НР может попросить правку или скрытие профиля.
 * Без адреса (NEXT_PUBLIC_CLAIM_EMAIL) блок скрыт целиком: пустой mailto
 * хуже отсутствия ссылки (SPEC_SFR4 §4). */
export function ClaimProfileLink({ authorId }: { authorId: string }) {
  if (!process.env.NEXT_PUBLIC_CLAIM_EMAIL) return null;
  return (
    <p className="flex items-center gap-2 px-1 text-[13px] text-fg-subtle">
      <UserRound className="size-3.5" aria-hidden strokeWidth={2} />
      <span>
        Это вы?{" "}
        <a href={claimProfileMailto(authorId)} className="text-accent hover:text-accent-hover">
          Редактировать или скрыть профиль
        </a>
      </span>
    </p>
  );
}
