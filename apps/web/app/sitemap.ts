import type { MetadataRoute } from "next";

import { listAllSupervisors } from "@/lib/api";

export const revalidate = 3600;

// Открытые страницы НР — органический канал (NEXT.md §1): sitemap по всему
// каталогу, чтобы поисковики находили их без внутренних ссылок.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const site = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  // На билде API может не быть (CI: сборка обязана проходить) — тогда снапшот
  // «только лендинг», его чинит пост-деплойная ревалидация (deploy/README.md).
  // В рантайме ошибка НЕ ловится: упавший рендер не заменяет последнюю полную
  // версию sitemap в ISR-кэше, а без неё отдаёт 500 — бот придёт позже
  // (REVIEW_SFR3 High №2: час неполного sitemap хуже, чем ретрай).
  const building = process.env.NEXT_PHASE === "phase-production-build";
  const supervisors = building
    ? await listAllSupervisors().catch(() => [])
    : await listAllSupervisors();
  return [
    { url: site, changeFrequency: "monthly", priority: 1 },
    ...supervisors.map((supervisor) => ({
      url: `${site}/supervisor/${supervisor.author_id}`,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
  ];
}
