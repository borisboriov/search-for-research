import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

// Кнопки по DESIGN_SYSTEM v2 §1: primary — акцентный фон, 13px 26px, Plex 500
// 16px, высота ≥48px; secondary — «бумага» с рамкой `--border`. Компактный
// размер — 10px 18px / 15px, но высота остаётся ≥44px (тап-таргет из
// DESIGN_HANDOFF важнее 40px из макета).
const buttonVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2.5 rounded-btn text-[16px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white hover:bg-accent-hover",
        secondary: "border border-border bg-surface text-fg hover:bg-bg",
        inverse: "bg-white text-accent-deep hover:bg-accent-soft",
      },
      size: {
        default: "min-h-12 px-[26px] py-[13px]",
        compact: "min-h-11 gap-2 px-[18px] py-2.5 text-[15px]",
      },
    },
    defaultVariants: { variant: "primary", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { buttonVariants };
