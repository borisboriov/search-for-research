import { test as base, expect } from "@playwright/test";
export { expect };
export type { Page } from "@playwright/test";

let nextStart = 0;
/** Functional browser runs against Caddy retain production rate limits.
 * Explicit pacing separates sequential scenarios; it does not retry assertions
 * or alter the intentional 429 test, and the worker count remains one. */
export const test = base.extend<{ requestBudget: void }>({
  requestBudget: [async ({ baseURL }, use) => {
    const interval = Number(process.env.SFR_E2E_MIN_TEST_INTERVAL_MS ?? "0");
    if (!Number.isFinite(interval) || interval < 0 || interval > 30000) throw new Error("SFR_E2E_MIN_TEST_INTERVAL_MS must be 0..30000");
    if (baseURL && interval > 0) {
      const delay = nextStart - performance.now();
      if (delay > 0) await new Promise(resolve => setTimeout(resolve, delay));
      nextStart = performance.now() + interval;
    }
    await use();
  }, { auto: true }],
});
