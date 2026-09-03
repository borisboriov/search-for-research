"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function BackLink() {
  const params = useSearchParams();
  const query = params.get("q");
  // Пришли с результатов (есть q) — назад к той же выдаче; иначе на лендинг.
  const href = query ? `/results?q=${encodeURIComponent(query)}` : "/";
  return (
    <Link
      href={href}
      className="flex min-h-11 items-center gap-2 self-start text-[14px] text-accent hover:text-accent-hover"
    >
      <ArrowLeft className="size-4" aria-hidden strokeWidth={2} />
      {query ? "К результатам" : "На главную"}
    </Link>
  );
}

export function BackToResults() {
  return (
    <Suspense>
      <BackLink />
    </Suspense>
  );
}
