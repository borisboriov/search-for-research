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
  expect(html).toContain("Natural Language Processing");
  expect(html).toMatch(/<title>Ivan Smirnov — МФТИ \| Search for Research<\/title>/);
  expect(html).toContain('rel="canonical"');
  expect(html).toContain('property="og:title"');
});

test("sitemap.xml перечисляет все профили каталога", async ({ request }) => {
  const [sitemap, health] = await Promise.all([
    request.get("/sitemap.xml"),
    request.get("http://127.0.0.1:8000/api/health"),
  ]);
  const xml = await sitemap.text();
  const { profiles_count } = (await health.json()) as { profiles_count: number };
  const urls = xml.match(/\/supervisor\//g) ?? [];
  expect(urls.length).toBe(profiles_count);
});

test("robots.txt: каталог открыт, выдача и API закрыты", async ({ request }) => {
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain("Disallow: /results");
  expect(robots).toContain("Disallow: /api/");
  expect(robots).toContain("sitemap.xml");
});
