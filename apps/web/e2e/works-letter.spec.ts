import { expect, test } from "@playwright/test";

import { DESKTOP, KNOWN_AUTHOR_ID, screenshot } from "./helpers";

// Состояния без работ и неизвестного года — существующая dev-only витрина.
// Реальные результаты поиска не подменяются ради удобного профиля.
test.describe("работы и подготовка письма", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ viewport: DESKTOP, permissions: ["clipboard-read", "clipboard-write"] });

  test("работы по году, явное подтверждение выбора и копирование", async ({ page }) => {
    await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}`);
    await expect(page.getByRole("heading", { name: "Выбранные работы" })).toBeVisible();
    await expect(page.getByText(/не полный список последних работ/)).toBeVisible();
    const select = page.getByRole("combobox", { name: "Работа для письма" });
    const draft = page.getByLabel("Черновик письма");
    const options = await select.locator("option").allTextContents();
    expect(options.length).toBeGreaterThan(2);
    const years = options.slice(1).map((text) => {
      const match = text.match(/^(\d{4}) ·/);
      return match ? Number(match[1]) : -Infinity;
    });
    expect(years).toEqual([...years].sort((a, b) => b - a));
    await expect(select).toHaveValue("0");
    await expect(draft).toContainText("Здравствуйте, [Имя Отчество]!");
    await expect(draft).not.toContainText("Прочитал");
    const confirm = page.getByRole("checkbox", { name: "Добавить выбранную работу в письмо" });
    await confirm.check();
    const suggestedTitle = options[1]!.slice(options[1]!.indexOf(" · ") + 3);
    await expect(draft).toContainText(`«${suggestedTitle}»`);
    await select.selectOption("1");
    await expect(confirm).not.toBeChecked();
    await expect(draft).not.toContainText("Прочитал");
    await confirm.check();
    const chosenTitle = options[2]!.slice(options[2]!.indexOf(" · ") + 3);
    await expect(draft).toContainText(`«${chosenTitle}»`);
    const expectedLetter = await draft.textContent();
    await page.getByRole("button", { name: "Скопировать письмо" }).click();
    await expect(page.getByRole("button", { name: "Скопировано" })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(expectedLetter);
    await expect(draft).toContainText("[какую задачу хочу решать / тема ВКР]");
    await screenshot(page, "pilot-profile-works-letter-desktop");
    await select.selectOption("");
    await expect(draft).not.toContainText("Прочитал");
    await expect(page.getByRole("checkbox")).toHaveCount(0);
  });

  test("копирование без работ и с неизвестным годом", async ({ page }) => {
    test.skip(Boolean(process.env.SFR_WEB_URL), "Dev-only состояния недоступны в локальном production-стеке; 404 проверяет pages.spec.ts");
    await page.goto("/dev/states");
    const noWorks = page.getByRole("region", { name: "Письмо: без работ" });
    await expect(noWorks.getByRole("combobox")).toHaveCount(0);
    const noWorksDraft = noWorks.getByLabel("Черновик письма");
    await expect(noWorksDraft).not.toContainText("Прочитал");
    await noWorks.getByRole("button", { name: "Скопировать письмо" }).click();
    await expect(noWorks.getByRole("button", { name: "Скопировано" })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(await noWorksDraft.textContent());
    const undated = page.getByRole("region", { name: "Письмо: неизвестный год" });
    await expect(undated.getByRole("option", { selected: true })).toContainText("год не указан");
    await expect(undated.getByText(/Годы работ неизвестны/)).toBeVisible();
    await undated.getByRole("checkbox").check();
    const undatedDraft = undated.getByLabel("Черновик письма");
    await expect(undatedDraft).toContainText("«Undated sample publication» —");
    await expect(undatedDraft).not.toContainText("null");
    await undated.getByRole("button", { name: "Скопировать письмо" }).click();
    await expect(undated.getByRole("button", { name: "Скопировано" })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(await undatedDraft.textContent());
  });
});

for (const width of [375, 390]) {
  test(`тема в мобильной карточке открывает поиск вместо профиля (${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    const searches: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname === "/api/match") {
        searches.push((request.postDataJSON() as { query: string }).query);
      }
    });
    await page.goto("/results?q=" + encodeURIComponent("машинное обучение"));
    const topic = page.getByRole("list", { name: "Ключевые темы" }).first().getByRole("link").first();
    await expect(topic).toBeVisible({ timeout: 15_000 });
    const href = await topic.getAttribute("href");
    expect(href).toMatch(/^\/results\?q=/);
    await expect(topic).toHaveAttribute("rel", "nofollow");
    // Ссылка доступна поверх stretched-link. Наведение не запускает поиск.
    await page.waitForLoadState("networkidle");
    const countBefore = searches.length;
    await topic.hover();
    await page.waitForLoadState("networkidle");
    expect(searches.length).toBe(countBefore);
    await topic.click();
    await expect(page).toHaveURL(new RegExp(href!.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    await expect(page).not.toHaveURL(/\/supervisor\//);
    const originalTopic = new URL(href!, "http://localhost:3000").searchParams.get("q");
    // React StrictMode в dev повторяет mount/effect, поэтому число POST может быть два.
    await expect.poll(() => searches.slice(countBefore)).toContain(originalTopic);
    expect(searches.slice(countBefore).every((query) => query === originalTopic)).toBe(true);
  });
}

test("тема превью лендинга и тема SSR профиля ищут исходное название", async ({ page }) => {
  await page.goto("/");
  const previewTopic = page.getByRole("list", { name: "Ключевые темы" }).first().getByRole("link").first();
  await expect(previewTopic).toBeVisible({ timeout: 15_000 });
  const previewHref = await previewTopic.getAttribute("href");
  await previewTopic.click();
  await expect.poll(() => new URL(page.url()).searchParams.get("q")).toBe(
    new URL(previewHref!, "http://localhost:3000").searchParams.get("q"),
  );
  await expect(page).not.toHaveURL(/\/supervisor\//);
  await page.goto(`/supervisor/${KNOWN_AUTHOR_ID}`);
  const profileTopic = page.getByRole("list", { name: "Ключевые темы" }).getByRole("link").first();
  const profileHref = await profileTopic.getAttribute("href");
  await expect(profileTopic).toHaveAttribute("rel", "nofollow");
  await profileTopic.click();
  await expect.poll(() => new URL(page.url()).searchParams.get("q")).toBe(
    new URL(profileHref!, "http://localhost:3000").searchParams.get("q"),
  );
});
