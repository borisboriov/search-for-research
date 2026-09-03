import { cn } from "@/lib/utils";
import { initials } from "@/lib/utils";

/** Аватар-инициалы; serendipity — единственный случай тёплой палитры. */
export function AvatarInitials({
  name,
  serendipity = false,
  className,
}: {
  name: string;
  serendipity?: boolean;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full font-semibold",
        serendipity ? "bg-serendipity-soft text-serendipity" : "bg-accent-soft text-accent",
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}
