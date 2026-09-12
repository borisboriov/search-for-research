import Link from "next/link";

import { Logo } from "@/components/logo";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Ссылка «Научрукам» и аватар пользователя убраны до пилота — решение Бориса
// (SPEC_SFR3, шапка). В макете B «Научрукам» снова есть, но SPEC_SFR6 §0
// требует шапку «как на сайте», а страницы «Научрукам» в MVP по-прежнему нет:
// пункт не возвращаем (расхождение с макетом — в SFR6_REPORT).
export function SiteHeader({ variant = "app" }: { variant?: "landing" | "app" }) {
  return (
    <header
      className={cn(
        "flex items-center justify-between px-4 sm:px-16",
        variant === "landing" ? "py-3.5 sm:py-[18px]" : "border-b border-border py-3.5 sm:py-[18px]",
      )}
    >
      <Link href="/" className="rounded-btn focus-visible:outline-2 focus-visible:outline-accent">
        <Logo />
      </Link>
      <nav className="flex items-center gap-7" aria-label="Основная навигация">
        <Link
          href="/#how-it-works"
          className="hidden text-[15px] text-fg-muted hover:text-fg sm:block"
        >
          Как это работает
        </Link>
        {variant === "landing" && (
          <Link
            href="/#search"
            className={cn(buttonVariants({ size: "compact" }), "hidden sm:inline-flex")}
          >
            Подобрать научрука
          </Link>
        )}
      </nav>
    </header>
  );
}
