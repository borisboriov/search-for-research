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

// Серая зона (SPEC_SFR4 §0.9). Запрос менялся дважды: «computer science
// backend engineering» перестал быть посторонним на 12 вузах, а киноведение —
// после бэкфилла публикаций (полные тексты сдвинули всю шкалу вверх). После
// перекалибровки ревью SFR-5 зона — [0.32, 0.40), и в неё попадает
// музыковедение: top-1 0.391 при отсутствии музыковедов в каталоге.
// Тест хрупок по построению — окно живое, а индекс пересобирается; вынести
// пороги в env-профиль e2e решено в §0 следующей спеки (docs/NEXT.md).
test("академически звучащий запрос без ответа в корпусе — баннер, выдача остаётся", async ({
  page,
}) => {
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
