import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

// Кнопки по DESIGN_SYSTEM §1: primary — акцентный фон, 14px 26px, высота ≥44px
// (тап-таргет); secondary — белая с рамкой.
const buttonVariants = cva(
  "inline-flex min-h-11 cursor-pointer items-center justify-center gap-2.5 rounded-btn text-[16px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white hover:bg-accent-hover",
        secondary: "border border-border bg-surface text-fg hover:bg-bg",
        inverse: "bg-surface font-semibold text-accent-deep hover:bg-accent-soft",
      },
      size: {
        default: "px-[26px] py-3.5",
        compact: "px-5 py-2.5 text-[15px]",
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
