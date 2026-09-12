import { cn } from "@/lib/utils";

/** Знак «Совпадение»: две окружности с закрашенной общей зоной (design/logo/sfr-mark.svg).
 * Форма в направлении B не менялась — только цвет (`text-accent`, #0F5F5C). */
export function LogoMark({
  className,
  strokeWidth = 2.6,
}: {
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      className={className}
      aria-hidden
    >
      <circle cx="18" cy="24" r="12" />
      <circle cx="30" cy="24" r="12" />
      <path d="M24 13.6A12 12 0 0 1 24 34.4A12 12 0 0 1 24 13.6Z" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Лок-ап: знак + словесная часть Literata 500 (`font-display`, DESIGN_SYSTEM v2
 * §1). mono — для футера (цвет текста). Знак в шапке — 26px, как в макете B;
 * обводка чуть толще токена v1, иначе на 26px знак читается тоньше макета. */
export function Logo({ mono = false }: { mono?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark
        className={cn(mono ? "size-[18px] text-fg" : "size-[26px] text-accent")}
        strokeWidth={mono ? 3.8 : 3.4}
      />
      <span
        className={cn(
          "font-display font-medium tracking-[-0.015em] text-fg",
          mono ? "text-[15px]" : "text-[18px] sm:text-[21px]",
        )}
      >
        Search for Research
      </span>
    </span>
  );
}
