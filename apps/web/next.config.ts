import type { NextConfig } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";

// canonical, OG и sitemap инлайнятся на билде из NEXT_PUBLIC_SITE_URL —
// забытая переменная означала бы прод с localhost-ссылками (REVIEW_SFR3
// Medium). Падаем на прод-билде, а не молча подставляем fallback.
export default function nextConfig(phase: string): NextConfig {
  if (phase === PHASE_PRODUCTION_BUILD && !process.env.NEXT_PUBLIC_SITE_URL) {
    throw new Error(
      "NEXT_PUBLIC_SITE_URL не задан: canonical/OG/sitemap уйдут на localhost. " +
        "Прод-сборка: NEXT_PUBLIC_SITE_URL=https://<домен> npm run build.",
    );
  }
  return {
    // Артефакт для деплоя SFR-4: standalone-сборка без node_modules хоста.
    output: "standalone",
    poweredByHeader: false,
    // Плавающий индикатор dev-инструментов пачкал скриншоты визуальной сверки.
    devIndicators: false,
    async headers() {
      return [
        {
          source: "/:path*",
          headers: [
            { key: "X-Content-Type-Options", value: "nosniff" },
            { key: "X-Frame-Options", value: "DENY" },
            { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
            { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          ],
        },
      ];
    },
  };
}
