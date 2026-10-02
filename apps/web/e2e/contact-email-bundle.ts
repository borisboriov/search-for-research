import path from "node:path";
import type { Page } from "./fixtures";

let bundle: Promise<string> | undefined;
async function buildFixture(): Promise<string> {
  const { build } = await import("vite");
  const root = path.resolve(__dirname, "..");
  const result = await build({
    configFile: false, root, logLevel: "error",
    resolve: { alias: { "@": root } },
    define: {
      "process.env.NODE_ENV": JSON.stringify("production"),
      "process.env.NEXT_PUBLIC_SFR_RELEASE": JSON.stringify("synthetic-contact-fixture"),
    },
    build: {
      write: false, minify: false,
      lib: { entry: path.join(__dirname, "contact-email-fixture.tsx"), formats: ["iife"], name: "SyntheticContactFixture" },
    },
  });
  const output = Array.isArray(result) ? result[0] : result;
  if (!("output" in output)) throw new Error("Expected one fixture bundle");
  const chunk = output.output.find(item => item.type === "chunk");
  if (!chunk || chunk.type !== "chunk") throw new Error("Missing fixture JavaScript");
  return chunk.code;
}

/** Intercepted HTML and JS exist only in this Playwright page, never on a server. */
export async function openContactEmailFixture(page: Page): Promise<void> {
  bundle ??= buildFixture();
  const code = await bundle;
  await page.route("**/__sfr_test_contact_bundle.js", route => route.fulfill({ contentType: "text/javascript; charset=utf-8", body: code }));
  await page.route("**/supervisor/__sfr_test_contact__", route => route.fulfill({
    contentType: "text/html; charset=utf-8", body: '<!doctype html><html><head><meta charset="utf-8"><title>Synthetic component fixture</title></head><body><main id="fixture"></main><script src="/__sfr_test_contact_bundle.js"></script></body></html>',
  }));
  await page.goto("/supervisor/__sfr_test_contact__");
}
