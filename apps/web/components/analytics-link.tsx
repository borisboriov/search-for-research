"use client";
import Link from "next/link";
import { linkProfile, prepareSearch } from "@/lib/analytics";

export function TopicLink({ topic, children, className }: { topic: string; children: React.ReactNode; className?: string }) {
  const href = `/results?q=${encodeURIComponent(topic)}`;
  return <Link href={href} prefetch={false} rel="nofollow" className={className} onClick={event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    void prepareSearch(topic, "topic");
  }}>{children}</Link>;
}
export function ProfileLink({ href, author, search, position, children, className, label }: { href: string; author: string; search?: string; position?: number; children?: React.ReactNode; className?: string; label?: string }) {
  return <Link href={href} className={className} aria-label={label} onClick={event => {
    if (!search || !position || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    void linkProfile(author, search, position);
  }}>{children}</Link>;
}
