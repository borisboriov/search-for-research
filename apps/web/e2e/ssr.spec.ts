import { expect, test } from "@playwright/test";

import { KNOWN_AUTHOR_ID, KNOWN_AUTHOR_NAME } from "./helpers";

// SSR-контур (SPEC_SFR3 §3): полный HTML профиля без JS, sitemap со всеми
// профилями, robots.txt закрывает /results и /api.
test("HTML профиля содержит имя, вуз, темы и метатеги до гидратации", async ({ request }) => {
  const response = await request.get(`/supervisor/${KNOWN_AUTHOR_ID}`);
  expect(response.status()).toBe(200);
  const html = await response.text();
  expect(html).toContain(KNOWN_AUTHOR_NAME);
  expect(html).toContain("МФТИ");
  expect(html).toContain("Topic Modeling");
  expect(html).toMatch(/<title>Konstantin Vorontsov — МФТИ \| Search for Research<\/title>/);
  expect(html).toContain('rel="canonical"');
  expect(html).toContain('property="og:title"');
});

test("sitemap.xml перечисляет все профили каталога", async ({ request }) => {
  // Размер каталога берём с лендинга, а не из API напрямую: у боевой
  // компоновки API снаружи недоступен по дизайну (SFR-4), а лендинг
  // рендерит то же число сервером из /api/health. Заодно проверяется, что
  // витрина и sitemap говорят об одном каталоге.
  const [sitemap, landing] = await Promise.all([request.get("/sitemap.xml"), request.get("/")]);
  const html = await landing.text();
  const stat = html.match(/>([\d\u00a0\s]+)<\/span><span[^>]*>научрук\S* в каталоге/);
  expect(stat, "лендинг не показывает счётчик каталога — API отвечает?").not.toBeNull();
  const profilesCount = Number(stat![1].replace(/[\s\u00a0]/g, ""));
  const urls = (await sitemap.text()).match(/\/supervisor\//g) ?? [];
  expect(urls.length).toBe(profilesCount);
});

test("robots.txt: каталог открыт, выдача и API закрыты", async ({ request }) => {
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain("Disallow: /results");
  expect(robots).toContain("Disallow: /api/");
  expect(robots).toContain("sitemap.xml");
});
