import { defineConfig } from "@playwright/test";

// e2e идут против живого API (make api) и дев-сервера Next: локальный прогон,
// в CI не запускаются (SPEC_SFR3 §5). Скриншоты складываются в e2e/screenshots
// (gitignored) — из них собирается визуальная сверка для отчёта.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: process.env.SFR_WEB_URL ?? "http://localhost:3000",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
