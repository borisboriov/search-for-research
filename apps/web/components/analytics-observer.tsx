"use client";
import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { analyticsSession, emitEvent, observeProfile, whenVisible } from "@/lib/analytics";

export function VisitObserver() {
  const path = usePathname();
  useEffect(() => whenVisible(() => {
    void analyticsSession().then(s => { if (!s.started) emitEvent("visit_started", {}, null); });
  }), [path]);
  return null;
}
export function ProfileObserver({ authorId }: { authorId: string }) {
  const seen = useRef<string | null>(null);
  useEffect(() => whenVisible(() => { if (seen.current !== authorId) { seen.current = authorId; void observeProfile(authorId); } }), [authorId]);
  return null;
}
