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
  const seen = useRef(false);
  useEffect(() => whenVisible(() => { if (!seen.current) { seen.current = true; void observeProfile(authorId); } }), [authorId]);
  return null;
}
