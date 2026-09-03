import * as React from "react";

import { cn } from "@/lib/utils";

/** Карточка по токенам: белая поверхность, 1px граница, радиус 14px. */
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-card border border-border bg-surface", className)}
      {...props}
    />
  );
}
