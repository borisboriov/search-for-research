import { UserRound } from "lucide-react";

import { claimProfileMailto } from "@/lib/letter";

/** «Это вы?» — юр. контур: НР может попросить правку или скрытие профиля. */
export function ClaimProfileLink({ authorId }: { authorId: string }) {
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
