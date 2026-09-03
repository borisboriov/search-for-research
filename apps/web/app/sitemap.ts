import type { MetadataRoute } from "next";

import { listAllSupervisors } from "@/lib/api";

export const revalidate = 3600;

// Открытые страницы НР — органический канал (NEXT.md §1): sitemap по всему
// каталогу, чтобы поисковики находили их без внутренних ссылок.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const site = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  const supervisors = await listAllSupervisors();
  return [
    { url: site, changeFrequency: "monthly", priority: 1 },
    ...supervisors.map((supervisor) => ({
      url: `${site}/supervisor/${supervisor.author_id}`,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
  ];
}
