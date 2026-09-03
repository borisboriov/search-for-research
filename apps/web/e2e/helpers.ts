import type { Page } from "@playwright/test";

export const DESKTOP = { width: 1440, height: 900 };
export const MOBILE = { width: 390, height: 844 };

// Реальный профиль из превью лендинга (lib/preview.ts) — стабильный id каталога.
export const KNOWN_AUTHOR_ID = "A5070267730";
export const KNOWN_AUTHOR_NAME = "Ivan Smirnov";

export async function screenshot(page: Page, name: string): Promise<void> {
  // Скриншоты сверяются с макетами глазами — дождаться шрифтов обязательно,
  // иначе Spectral/Golos на снимке подменяются фолбэком.
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
