import { expect, test } from "@playwright/test";

const longInstitution = "Московский государственный технический университет имени Н. Э. Баумана";

for (const width of [375, 390]) {
  test.describe(`фильтры ${width}px`, () => {
    test.use({ viewport: { width, height: 844 } });

    test("длинная организация, h-index, сортировка, применение и сброс", async ({ page }) => {
      // Реальные карточки/контракт API, детерминированные организации и h-index
      // проверяют механику фильтра, не качество или границы ранжирования.
      await page.route("**/api/match", async (route) => {
        const response = await route.fetch();
        const payload = await response.json();
        const first = payload.results[0];
        expect(first).toBeDefined();
        payload.confidence = "ok";
        payload.below_threshold = false;
        payload.results = [
          { ...first, author_id: "filter-first", name: "Первый исследователь", institution: longInstitution, h_index: 10, rank: 1 },
          { ...first, author_id: "filter-second", name: "Второй исследователь", institution: longInstitution, h_index: 50, rank: 2 },
          { ...first, author_id: "filter-third", name: "Третий исследователь", institution: "МФТИ", h_index: 60, rank: 3 },
        ];
        await route.fulfill({ response, json: payload });
      });
      await page.goto("/results?q=" + encodeURIComponent("теплообмен"));
      await expect(page.getByRole("heading", { name: /Нашли 3/ })).toBeVisible();
      await page.getByRole("button", { name: "Фильтры", exact: true }).click();
      const dialog = page.getByRole("dialog");
      await dialog.getByRole("combobox", { name: "Организация: все" }).selectOption(longInstitution);
      await dialog.getByRole("combobox", { name: "h-index: любой" }).selectOption("20");
      await dialog.getByRole("combobox", { name: "По совпадению" }).selectOption("h_index");
      const geometry = await dialog.evaluate((el) => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
      expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width);
      for (const name of ["Применить", "Сбросить", "Закрыть"]) {
        const action = dialog.getByRole("button", { name, exact: true });
        await expect(action).toBeInViewport();
        const box = await action.boundingBox();
        expect(box!.x).toBeGreaterThanOrEqual(0);
        expect(box!.x + box!.width).toBeLessThanOrEqual(width);
      }
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: `e2e/screenshots/filters-after-${width}.png` });
      await dialog.getByRole("button", { name: "Применить", exact: true }).click();
      await expect(dialog).not.toBeVisible();
      await expect(page.getByRole("heading", { name: /Нашли 1/ })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Второй исследователь" })).toBeVisible();

      await page.getByRole("button", { name: "Фильтры", exact: true }).click();
      await dialog.getByRole("button", { name: "Сбросить", exact: true }).click();
      await expect(dialog.getByRole("combobox", { name: "Организация: все" })).toHaveValue("");
      await expect(dialog.getByRole("combobox", { name: "h-index: любой" })).toHaveValue("0");
      await expect(dialog.getByRole("combobox", { name: "По совпадению" })).toHaveValue("score");
      await dialog.getByRole("combobox", { name: "По совпадению" }).selectOption("h_index");
      await dialog.getByRole("button", { name: "Применить", exact: true }).click();
      await expect(page.getByRole("heading", { name: /Нашли 3/ })).toBeVisible();
      await expect(page.getByRole("heading", { level: 3 }).first()).toHaveText("Третий исследователь");
      await page.getByRole("button", { name: "Фильтры", exact: true }).click();
      await dialog.getByRole("button", { name: "Сбросить", exact: true }).click();
      await dialog.getByRole("button", { name: "Применить", exact: true }).click();
      await expect(page.getByRole("heading", { level: 3 }).first()).toHaveText("Первый исследователь");
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);

      // Закрытие без применения не меняет выдачу, следующий вход восстанавливает значения.
      await page.getByRole("button", { name: "Фильтры", exact: true }).click();
      await dialog.getByRole("combobox", { name: "h-index: любой" }).selectOption("50");
      await dialog.getByRole("button", { name: "Закрыть", exact: true }).click();
      await expect(page.getByRole("heading", { name: /Нашли 3/ })).toBeVisible();
      await page.getByRole("button", { name: "Фильтры", exact: true }).click();
      await expect(dialog.getByRole("combobox", { name: "h-index: любой" })).toHaveValue("0");
    });
  });
}
