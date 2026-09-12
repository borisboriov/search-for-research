import { cn } from "@/lib/utils";

/**
 * Ярлык-пилюля разделов лендинга (DESIGN_SYSTEM v2 §3): точка `--accent`,
 * рамка `--border`, фон `--surface`, 12px Plex 500 uppercase 0.08em.
 * Заменил кружки «1 / 2 / 3» в «Как это работает» (S-06) — заливок акцентом
 * на экран должно быть две, и кружки были третьей.
 */
export function PillLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p
      className={cn(
        "inline-flex items-center gap-2 self-start rounded-full border border-border bg-surface py-[5px] pr-3 pl-2.5 text-[12px] font-medium tracking-[0.08em] text-fg-muted uppercase",
        className,
      )}
    >
      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-accent" />
      {children}
    </p>
  );
}
