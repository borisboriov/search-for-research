import { expect, test } from "@playwright/test";

import { DESKTOP, KNOWN_AUTHOR_ID, KNOWN_AUTHOR_NAME, MOBILE, screenshot } from "./helpers";

// Скриншоты трёх страниц на 1440 и 390 — материал визуальной сверки с
// design/mockups/*.png (SPEC_SFR3 §5). Файлы в e2e/screenshots (gitignored).
for (const [label, viewport] of [
  ["1440", DESKTOP],
  ["390", MOBILE],
] as const) {
  test.describe(`страницы на ${label}`, () => {
    test.use({ viewport });

    test(`лендинг (${label})`, async ({ page }) => {
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1 })).toContainText(
        "Научный руководитель под твою тему",
      );
      // Превью подборки — реальные профили каталога
      await expect(page.getByText(KNOWN_AUTHOR_NAME)).toBeVisible();
      await screenshot(page, `landing-${label}`);
    });

    test(`результаты (${label})`, async ({ page }) => {
      await page.goto("/results?q=" + encodeURIComponent("машинное обучение для анализа текстов"));
      await expect(page.getByRole("heading", { name: /Нашли \d+ научрук/ })).toBeVisible({
        timeout: 15_000,
      });
      await screenshot(page, `results-${label}`);
    });

    test(`пустая выдача (${label})`, async ({ page }) => {
      await page.goto("/results?q=" + encodeURIComponent("как починить стиральную машину"));
      await expect(page.getByText("Уверенных совпадений нет")).toBeVisible({ timeout: 15_000 });
      await screenshot(page, `results-empty-${label}`);
    });

    test(`профиль НР (${label})`, async ({ page }) => {
      await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}?score=0.62&grade=high`);
      await expect(page.getByRole("heading", { level: 1 })).toContainText(KNOWN_AUTHOR_NAME);
      await expect(page.getByText("Наукометрия")).toBeVisible();
      // Пришли «с результатов»: грейд словом, процента на профиле нет (решение 11.09)
      await expect(page.getByText("высокое совпадение")).toBeVisible();
      await expect(page.getByText("62%")).toHaveCount(0);
      // Плашка происхождения данных над метриками (P-08): дата — из /health
      await expect(page.getByRole("button", { name: /Данные: OpenAlex · обновлено/ })).toBeVisible();
      await screenshot(page, `supervisor-${label}`);
    });

    test(`витрина состояний (${label})`, async ({ page }) => {
      // Против прод-стека (SFR_WEB_URL, make deploy-local) витрина обязана
      // отдавать 404 — проверяем сам гард; в dev она открыта.
      if (process.env.SFR_WEB_URL) {
        const response = await page.goto("/dev/states");
        expect(response?.status()).toBe(404);
        return;
      }
      await page.goto("/dev/states");
      await expect(page.getByText("неожиданный вариант").filter({ visible: true }).first()).toBeVisible();
      await screenshot(page, `states-${label}`);
    });
  });
}

test("профиль без ?score и ?grade не показывает бейдж совпадения", async ({ page }) => {
  await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}`);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(KNOWN_AUTHOR_NAME);
  await expect(page.getByText(/совпадение/)).toHaveCount(0);
});

test("строка происхождения тем — внутри блока «Чем занимается» (P-09)", async ({ page }) => {
  await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}`);
  await expect(
    page.getByText("Темы посчитаны по публикациям в OpenAlex; научный руководитель их не подтверждал"),
  ).toBeVisible();
});

test("битый id — 404-страница в стиле сервиса", async ({ page }) => {
  const response = await page.goto("/supervisor/NOPE123");
  expect(response?.status()).toBe(404);
  await expect(page.getByText("Такой страницы нет")).toBeVisible();
  await screenshot(page, "not-found-1440");
});
