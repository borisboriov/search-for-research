import { expect, test } from "@playwright/test";

import { catalogueCount, COLD_START, KNOWN_AUTHOR_ID, KNOWN_AUTHOR_NAME } from "./helpers";

// SSR-контур (SPEC_SFR3 §3): полный HTML профиля без JS, sitemap со всеми
// профилями, robots.txt закрывает /results и /api.
test("HTML профиля содержит имя, вуз, темы и метатеги до гидратации", async ({ request }) => {
  const response = await request.get(`/supervisor/${KNOWN_AUTHOR_ID}`);
  expect(response.status()).toBe(200);
  const html = await response.text();
  expect(html).toContain(KNOWN_AUTHOR_NAME);
  expect(html).toContain("МФТИ");
  expect(html).toContain("Topic Modeling");
  expect(html).toContain('href="/results?q=Topic%20Modeling"');
  expect(html).toContain(">Тематическое моделирование</a>");
  expect(html).toContain("Ключевые темы по публикациям: Тематическое моделирование");
  expect(html).toMatch(/<title>Konstantin Vorontsov — МФТИ \| Search for Research<\/title>/);
  expect(html).toContain('rel="canonical"');
  expect(html).toContain('property="og:title"');
});

test("sitemap.xml перечисляет все профили каталога", async ({ request }) => {
  // Размер каталога берём с лендинга, а не из API напрямую: у боевой
  // компоновки API снаружи недоступен по дизайну (SFR-4), а лендинг
  // рендерит то же число сервером из /api/health. Заодно проверяется, что
  // витрина и sitemap говорят об одном каталоге.
  // На холодном старте обе страницы могут прийти снимком без данных API —
  // повторяем пару запросов, пока счётчик не появится и не сойдётся с sitemap.
  await expect(async () => {
    const [sitemap, landing] = await Promise.all([request.get("/sitemap.xml"), request.get("/")]);
    const profilesCount = catalogueCount(await landing.text());
    expect(profilesCount, "лендинг не показывает счётчик каталога — API отвечает?").not.toBeNull();
    const urls = (await sitemap.text()).match(/\/supervisor\//g) ?? [];
    expect(urls.length).toBe(profilesCount);
  }).toPass(COLD_START);
});

test("robots.txt: каталог открыт, выдача и API закрыты", async ({ request }) => {
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain("Disallow: /results");
  expect(robots).toContain("Disallow: /api/");
  expect(robots).toContain("sitemap.xml");
});
