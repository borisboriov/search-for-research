import { expect, test } from "@playwright/test";

import { DESKTOP, KNOWN_AUTHOR_ID, screenshot } from "./helpers";

test.use({ viewport: DESKTOP });

for (const length of [499, 500]) {
  test(`запрос ${length} символов отправляется`, async ({ page }) => {
    await page.goto("/");
    await page.getByRole("textbox", { name: "Описание научных интересов" }).fill("я".repeat(length));
    await expect(page.getByText(`${length} / 500`, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Подобрать научрука" }).click();
    await expect(page).toHaveURL(/\/results\?q=/);
    expect(new URL(page.url()).searchParams.get("q")).toHaveLength(length);
  });
}

test("501 символ и длинная вставка не обрезаются, отправка заблокирована", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  let requests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/match")) requests++;
  });
  await page.goto("/");
  const textarea = page.getByRole("textbox", { name: "Описание научных интересов" });
  await textarea.fill("я".repeat(501));
  await expect(page.getByRole("alert").filter({ hasText: "Убери" })).toHaveText(/Убери 1 символ/);
  await expect(page.getByRole("button", { name: "Подобрать научрука" })).toBeDisabled();
  await textarea.press("ControlOrMeta+Enter");
  await expect(page).toHaveURL(/\/$/);
  await textarea.fill("");
  const long = Array.from({ length: 120 }, () => "тема исследования").join("\n");
  await page.evaluate((text) => navigator.clipboard.writeText(text), long);
  await textarea.focus();
  await textarea.press("ControlOrMeta+V");
  await expect(textarea).toHaveValue(long);
  await expect(page.getByText(`${long.length} / 500`, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Подобрать научрука" })).toBeDisabled();
  const size = await textarea.evaluate((field) => ({ height: field.clientHeight, content: field.scrollHeight }));
  expect(size.height).toBeLessThanOrEqual(320);
  expect(size.content).toBeGreaterThan(size.height);
  expect(requests).toBe(0);
});

test("нажатие текущего запроса непосредственно включает редактирование", async ({ page }) => {
  const query = "физика элементарных частиц";
  await page.goto(`/results?q=${encodeURIComponent(query)}`);
  await page.getByRole("button", { name: `Редактировать текущий запрос: ${query}` }).click();
  const textarea = page.getByRole("textbox");
  await expect(textarea).toHaveValue(query);
  await expect(textarea).toBeFocused();
  await textarea.fill("квантовые материалы и сверхпроводимость");
  await page.getByRole("button", { name: "Подобрать научрука" }).click();
  await expect(page).toHaveURL(/\/results\?q=/);
  await expect(page.getByRole("button", { name: /Редактировать текущий запрос: квантовые материалы/ })).toBeVisible();
});

test("объяснение грейда доступно с клавиатуры на выдаче и в профиле", async ({ page }) => {
  await page.goto(`/results?q=${encodeURIComponent("физика элементарных частиц")}`);
  const summary = page.locator("summary").filter({ hasText: /совпадение/ }).first();
  await expect(summary).toBeVisible({ timeout: 15_000 });
  await summary.focus();
  await summary.press("Enter");
  await expect(page.getByText(/Поиск сравнивает твой запрос/).filter({ visible: true }).first()).toBeVisible();
  await summary.press("Enter");
  await expect(page.getByText(/Поиск сравнивает твой запрос/).filter({ visible: true })).toHaveCount(0);

  await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}?score=0.45&grade=medium&q=${encodeURIComponent("анализ текстов")}`);
  const profileSummary = page.getByLabel("среднее совпадение: что это значит", { exact: true });
  // ISR/Suspense может сначала отдать скрытый фрагмент потока HTML.
  await expect(profileSummary).toBeVisible();
  await profileSummary.focus();
  await expect(profileSummary).toBeFocused();
  await profileSummary.press("Enter");
  await expect(page.getByText(/Среднее совпадение: по оценке поиска/)).toBeVisible();
  await expect(page.getByText(/^\d+%$/)).toHaveCount(0);
});

test("лендинг уточняет темы и подготовку письма без гарантии времени и размера каталога", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Научный руководитель под твою тему");
  await expect(page.getByText("До 10 научруков из разных вузов со степенью совпадения, темами исследований и наукометрией.", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Подготовь письмо", exact: true })).toBeVisible();
  await expect(page.getByText("Открой профиль, изучи выбранные работы и подготовь черновик письма по шаблону. Отправить его можно самостоятельно.", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Найди исследователей, близких к твоей теме", exact: true })).toBeVisible();
  await expect(page.getByText(/за минуту|меньше чем за секунду|из сотен|3–12 недель/)).toHaveCount(0);
});

for (const width of [375, 390]) {
  test(`объяснение в профиле не расширяет страницу на ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}?score=0.45&grade=medium`);
    const summary = page.getByLabel("среднее совпадение: что это значит", { exact: true });
    await expect(summary).toBeVisible();
    await summary.click();
    await expect(page.getByText(/Среднее совпадение: по оценке поиска/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await screenshot(page, `pilot-profile-grade-after-${width}`);
  });

  test(`поле растёт и ограничивает высоту на ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const textarea = page.getByRole("textbox", { name: "Описание научных интересов" });
    const initialHeight = await textarea.evaluate((field) => field.clientHeight);
    await textarea.fill("Тема: исследование текстов.\n".repeat(60));
    const size = await textarea.evaluate((field) => ({ height: field.clientHeight, content: field.scrollHeight }));
    expect(size.height).toBeGreaterThan(initialHeight);
    expect(size.height).toBeLessThanOrEqual(Math.min(0.4 * 844, 320));
    expect(size.content).toBeGreaterThan(size.height);
    await expect(page.getByRole("button", { name: "Подобрать научрука" })).toBeDisabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });

  test(`слабые совпадения: советы, редактирование и раскрытие на ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    // Реальные карточки API; меняется только детерминированное состояние UI.
    await page.route("**/api/match", async (route) => {
      const response = await route.fetch();
      const payload = await response.json();
      payload.confidence = "weak";
      payload.below_threshold = false;
      for (const result of payload.results) result.grade = "low";
      await route.fulfill({ response, json: payload });
    });
    await page.goto(`/results?q=${encodeURIComponent("физика элементарных частиц")}`);
    await expect(page.getByText(/Совпадения слабые: запрос мало похож/)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Назови конкретную тему:/)).toBeVisible();
    await expect(page.getByText(/Добавь метод, который/)).toBeVisible();
    await expect(page.getByText(/Укажи объект исследования:/)).toBeVisible();
    await page.getByLabel("слабое совпадение: что это значит", { exact: true }).first().click();
    await expect(page.getByText(/Слабое совпадение: по оценке поиска/).first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await screenshot(page, `pilot-grade-after-${width}`);
    await page.getByRole("button", { name: "Изменить запрос", exact: true }).filter({ visible: true }).last().click();
    await expect(page.getByRole("textbox")).toBeFocused();
  });
}
