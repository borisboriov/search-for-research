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
      await expect(page.getByText(/Найдено \d+/).filter({ visible: true }).first()).toBeVisible({ timeout: 15_000 });
      await screenshot(page, `results-${label}`);
    });

    test(`пустая выдача (${label})`, async ({ page }) => {
      await page.goto("/results?q=" + encodeURIComponent("как починить стиральную машину"));
      await expect(page.getByText("Уверенных совпадений нет")).toBeVisible({ timeout: 15_000 });
      await screenshot(page, `results-empty-${label}`);
    });

    test(`профиль НР (${label})`, async ({ page }) => {
      await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}?score=0.62`);
      await expect(page.getByRole("heading", { level: 1 })).toContainText(KNOWN_AUTHOR_NAME);
      await expect(page.getByText("Наукометрия")).toBeVisible();
      await expect(page.getByText("62%")).toBeVisible(); // пришли «с результатов»
      await screenshot(page, `supervisor-${label}`);
    });

    test(`витрина состояний (${label})`, async ({ page }) => {
      await page.goto("/dev/states");
      await expect(page.getByText("неожиданный вариант").filter({ visible: true }).first()).toBeVisible();
      await screenshot(page, `states-${label}`);
    });
  });
}

test("профиль без ?score не показывает блок совпадения", async ({ page }) => {
  await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}`);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(KNOWN_AUTHOR_NAME);
  await expect(page.getByText("совпадение")).toHaveCount(0);
});

test("битый id — 404-страница в стиле сервиса", async ({ page }) => {
  const response = await page.goto("/supervisor/NOPE123");
  expect(response?.status()).toBe(404);
  await expect(page.getByText("Такой страницы нет")).toBeVisible();
  await screenshot(page, "not-found-1440");
});
