import { isIP } from "node:net";
import type { NextRequest } from "next/server";
import { UUID } from "./analytics-contract";

/** Bounded streaming read also protects requests without Content-Length. */
export async function readBody(request: NextRequest, limit: number): Promise<unknown> {
  const declared = Number(request.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > limit) throw new RangeError("body size");
  const reader = request.body?.getReader();
  if (!reader) throw new SyntaxError("body missing");
  const deadline = setTimeout(() => { void reader.cancel(); }, 5000);
  let size = 0;
  const chunks: Uint8Array[] = [];
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) throw new RangeError("body size");
      chunks.push(value);
    }
  } finally { clearTimeout(deadline); await reader.cancel().catch(() => {}); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}
export function proxyHeaders(request: NextRequest): Headers {
  const headers = new Headers({ "Content-Type": "application/json" });
  for (const name of ["X-SFR-Visit-ID", "X-SFR-Search-ID", "X-Request-ID"]) {
    const value = request.headers.get(name);
    if (value && UUID.test(value)) headers.set(name, value);
  }
  if (!headers.has("X-Request-ID")) headers.set("X-Request-ID", crypto.randomUUID());
  // Enabled only for the isolated Caddy → Next private network deployment.
  if (process.env.SFR_TRUST_PROXY === "1") {
    const forwarded = request.headers.get("x-sfr-client-ip") ?? request.headers.get("x-forwarded-for");
    if (forwarded && forwarded.length <= 64 && isIP(forwarded)) {
      headers.set("X-SFR-Client-IP", forwarded);
      headers.set("X-Forwarded-For", forwarded);
    }
  }
  for (const name of ["User-Agent", "Accept-Language"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value.slice(0, 512));
  }
  // URL parameters are deliberately omitted: they may carry tokens or query text.
  headers.set("X-SFR-Page-URL", `${request.nextUrl.origin}${request.nextUrl.pathname}`.slice(0, 2048));
  const referer = request.headers.get("referer");
  if (referer) {
    try { const url = new URL(referer); headers.set("X-SFR-Referer", `${url.origin}${url.pathname}`.slice(0, 2048)); } catch {}
  }
  return headers;
}
