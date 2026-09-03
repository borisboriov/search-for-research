import Link from "next/link";

import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";

// Ссылка «Научрукам» и аватар пользователя убраны до пилота — решение Бориса
// (SPEC_SFR3, шапка). Остаётся «Как это работает» → якорь на лендинге.
export function SiteHeader({ variant = "app" }: { variant?: "landing" | "app" }) {
  return (
    <header
      className={cn(
        "flex items-center justify-between px-5 sm:px-16",
        variant === "landing" ? "py-4 sm:py-[26px]" : "border-b border-border py-4 sm:py-[22px]",
      )}
    >
      <Link href="/" className="rounded-btn focus-visible:outline-2 focus-visible:outline-accent">
        <Logo compact={variant === "app"} />
      </Link>
      <nav className="flex items-center gap-8" aria-label="Основная навигация">
        <Link
          href="/#how-it-works"
          className="hidden text-[15px] text-fg-muted hover:text-fg sm:block"
        >
          Как это работает
        </Link>
        {variant === "landing" && (
          <Link
            href="/#search"
            className="hidden rounded-btn bg-accent px-5 py-2.5 text-[15px] font-medium text-white hover:bg-accent-hover sm:block"
          >
            Подобрать научрука
          </Link>
        )}
      </nav>
    </header>
  );
}
