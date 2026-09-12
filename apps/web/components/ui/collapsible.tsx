"use client";

import * as CollapsiblePrimitive from "@radix-ui/react-collapsible";

/** shadcn Collapsible без модификаций (DESIGN_SYSTEM v2 §5): им раскрывается
 * обрезанное название последней работы в карточке результата (P-15). */
export const Collapsible = CollapsiblePrimitive.Root;
export const CollapsibleTrigger = CollapsiblePrimitive.CollapsibleTrigger;
export const CollapsibleContent = CollapsiblePrimitive.CollapsibleContent;
