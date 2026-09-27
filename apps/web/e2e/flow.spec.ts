import { expect, test } from "@playwright/test";

import { DESKTOP } from "./helpers";

test.use({ viewport: DESKTOP });

// Главный пользовательский путь: лендинг → результаты → профиль → «К результатам».
test("лендинг → результаты → профиль → назад к результатам", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "Описание научных интересов" })
    .fill("сверхпроводимость и квантовые материалы");
  await page.getByRole("button", { name: "Подобрать научрука" }).click();

  await expect(page).toHaveURL(/\/results\?q=/);
  await expect(page.getByRole("heading", { name: /Нашли \d+ научрук/ })).toBeVisible({
    timeout: 15_000,
  });
  const firstCard = page.getByRole("link", { name: "Открыть профиль" }).first();
  await firstCard.click();

  await expect(page).toHaveURL(/\/supervisor\//);
  // Грейд словом передан с результатов (?grade=); процента на профиле нет
  await expect(page.getByText(/совпадение$/).first()).toBeVisible();
  await expect(page.getByText(/^\d+%$/)).toHaveCount(0);
  await expect(page.getByText("Написать научруку")).toBeVisible();

  await page.getByRole("link", { name: "К результатам" }).click();
  await expect(page).toHaveURL(/\/results\?q=/);
  await expect(page.getByRole("heading", { name: /Нашли \d+ научрук/ })).toBeVisible({
    timeout: 15_000,
  });
});

// Серая зона (SPEC_SFR4 §0.9): баннер «совпадения слабые», выдача остаётся,
// бейджи — словесные. Проверяется **отрисовка** состояния, а не пороги (#9):
// ответ /api/match настоящий (route.fetch — те же карточки, что отдаёт API, и
// дрейф контракта тест поймает), но confidence и грейды в нём подменены на
// серую зону. Раньше запрос подбирался так, чтобы живой top-1 попал в окно
// [none, weak) шириной 0.07, и любая пересборка индекса роняла тест без
// изменения кода. Попадание запросов в окно проверяют unit-тесты API
// (apps/api/tests, пороги из ApiSettings).
test("академически звучащий запрос без ответа в корпусе — баннер, выдача остаётся", async ({
  page,
}) => {
  await page.route("**/api/match", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.confidence = "weak";
    payload.below_threshold = false;
    for (const result of payload.results) result.grade = "low";
    await route.fulfill({ response, json: payload });
  });
  await page.goto(
    "/results?q=" + encodeURIComponent("музыковедение и гармонический анализ"),
  );
  await expect(page.getByText(/Совпадения слабые/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("heading", { name: /Нашли \d+ научрук/ })).toBeVisible();
  // бейджи при этом — словесные, «слабое совпадение», процентов на карточках нет
  // (первый матч — мобильный бейдж, на десктопе он скрыт — фильтруем по видимости)
  await expect(
    page.getByText("слабое совпадение").filter({ visible: true }).first(),
  ).toBeVisible();
});

test("запрос можно изменить прямо на результатах", async ({ page }) => {
  await page.goto(
    "/results?q=" + encodeURIComponent("физика элементарных частиц"),
  );
  await expect(page.getByRole("heading", { name: /Нашли \d+ научрук/ })).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: /Изменить запрос/ }).click();
  const textarea = page.getByRole("textbox");
  await textarea.fill("оптимизация маршрутов доставки");
  await page.getByRole("button", { name: "Подобрать научрука" }).click();
  await expect(page).toHaveURL(
    /%D0%BC%D0%B0%D1%80%D1%88%D1%80%D1%83%D1%82%D0%BE%D0%B2|маршрутов/,
  );
  await expect(page.getByRole("heading", { name: /Нашли \d+ научрук/ })).toBeVisible({
    timeout: 15_000,
  });
});

// 429 отдаёт прокси (лимит Caddy) с пустым телом — фронт показывает «слишком
// много запросов», а не «Сервис недоступен» (#23). Ответ подменён: настоящий
// лимит в e2e не выбивается, чтобы не зависеть от окна лимитера.
test("429 от лимитера — «слишком много запросов подряд», а не «сервис недоступен»", async ({
  page,
}) => {
  await page.route("**/api/match", (route) => route.fulfill({ status: 429, body: "" }));
  await page.goto("/results?q=" + encodeURIComponent("физика элементарных частиц"));
  await expect(page.getByText("Слишком много запросов подряд")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Сервис сейчас недоступен")).toHaveCount(0);
});
