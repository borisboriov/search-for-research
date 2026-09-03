import { cn } from "@/lib/utils";

/** Знак «Совпадение»: две окружности с закрашенной общей зоной (design/logo/sfr-mark.svg). */
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

/** Лок-ап: знак + словесная часть Spectral 500. mono — для футера (цвет текста). */
export function Logo({ mono = false, compact = false }: { mono?: boolean; compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark
        className={cn(mono ? "size-[22px] text-fg" : "text-accent", compact ? "size-[30px]" : "size-8")}
        strokeWidth={mono ? 2.8 : 2.6}
      />
      <span
        className={cn(
          "font-display font-medium tracking-[-0.015em] text-fg",
          mono ? "text-[16px]" : compact ? "text-[18px] sm:text-[21px]" : "text-[18px] sm:text-[22px]",
        )}
      >
        Search for Research
      </span>
    </span>
  );
}
