import * as React from "react";

import { cn } from "@/lib/utils";

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "w-full resize-none border-none bg-transparent text-[16px] leading-normal text-fg outline-none placeholder:text-fg-subtle",
        className,
      )}
      {...props}
    />
  );
}
