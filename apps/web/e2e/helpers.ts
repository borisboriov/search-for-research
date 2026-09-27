import type { Page } from "@playwright/test";

export const DESKTOP = { width: 1440, height: 900 };
export const MOBILE = { width: 390, height: 844 };

// Реальный профиль из превью лендинга (lib/preview.ts) — стабильный id каталога.
export const KNOWN_AUTHOR_ID = "A5050048876";
export const KNOWN_AUTHOR_NAME = "Konstantin Vorontsov";

// Холодный старт (#26): первый рендер лендинга и sitemap может уйти до ответа
// /api/health — без счётчика каталога и превью. API снаружи закрыт (SFR-4),
// поэтому ждём не /api/health, а сами страницы: проверку целиком повторяем,
// пока она не пройдёт, с ограничением по времени — без фиксированных пауз.
export const COLD_START = { timeout: 60_000, intervals: [500, 1_000, 2_000, 5_000] };

/** Число научруков со счётчика лендинга; null — счётчика в HTML нет. */
export function catalogueCount(html: string): number | null {
  const stat = html.match(/>([\d\u00a0\s]+)<\/span><span[^>]*>научрук\S* в каталоге/);
  return stat ? Number(stat[1].replace(/[\s\u00a0]/g, "")) : null;
}

export async function screenshot(page: Page, name: string): Promise<void> {
  // Скриншоты сверяются с макетами глазами — дождаться шрифтов обязательно,
  // иначе Literata/IBM Plex Sans на снимке подменяются фолбэком.
  await page.evaluate(() => document.fonts.ready);
  // Дождаться конца reveal-анимации списка, иначе карточки на снимке полупрозрачные.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        // бесконечные (skeleton pulse) не ждём — они не заканчиваются никогда
        .filter((animation) => animation.effect?.getTiming().iterations !== Infinity)
        .map((animation) => animation.finished.catch(() => undefined)),
    ),
  );
  await page.screenshot({ path: `e2e/screenshots/${name}.png`, fullPage: true });
}
