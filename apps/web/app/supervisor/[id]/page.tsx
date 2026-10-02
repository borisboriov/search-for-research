import { ProfileObserver } from "@/components/analytics-observer";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BackToResults } from "@/components/back-to-results";
import { ClaimProfileLink } from "@/components/claim-profile-link";
import { ContactCard } from "@/components/contact-card";
import { MetricsCard } from "@/components/metrics-card";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { SupervisorHeader } from "@/components/supervisor-header";
import { Card } from "@/components/ui/card";
import { WorksList } from "@/components/works-list";
import { getHealth, getSupervisor } from "@/lib/api";
import { topicLabel } from "@/lib/topics";
import { catalogueDate, formatIndexDate, institutionShort } from "@/lib/utils";

// ISR, а не SSG: страницы рендерятся по запросу и кэшируются на час, поэтому
// сборка не требует живого API, а каталог (меняется раз в семестр) не устаревает
// дольше часа (docs/DECISIONS.md: ISR vs SSG).
export const revalidate = 3600;
export const dynamicParams = true;

export function generateStaticParams(): Array<{ id: string }> {
  return []; // ничего не пререндерим на сборке — API на билд-машине не обязателен
}

interface PageProps {
  params: Promise<{ id: string }>;
}

// Формат OpenAlex author id: любая другая строка — мгновенный 404 без похода
// в API, чтобы перебор мусорных id не грузил бэкенд и не раздувал ISR-кэш
// (REVIEW_SFR3 Medium). getSupervisor при этом бросает на сеть/5xx — страница
// отвечает 500 через error boundary и не кэшируется, а 404 остаётся только
// за настоящим «нет такого НР».
const AUTHOR_ID = /^A\d{4,12}$/;

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  if (!AUTHOR_ID.test(id)) return { title: "Профиль не найден" };
  // Ошибку API глотаем только здесь: упавший generateMetadata обходит
  // error boundary и рендерит безликую 500 Next; пусть бросает сам рендер
  // страницы — тогда пользователь видит наш error.tsx (а статус всё равно 500).
  const card = await getSupervisor(id).catch(() => null);
  if (card === null) return { title: "Профиль не найден" };
  const university = institutionShort(card.institution);
  const title = university ? `${card.name} — ${university}` : card.name;
  const description = `Научный руководитель${university ? `, ${university}` : ""}${
    card.position ? `, ${card.position}` : ""
  }. Ключевые темы: ${card.topics.slice(0, 5).map(topicLabel).join(", ")}.`;
  return {
    title,
    description,
    alternates: { canonical: `/supervisor/${card.author_id}` },
    openGraph: {
      title: `${title} | Search for Research`,
      description,
      url: `/supervisor/${card.author_id}`,
      type: "profile",
      siteName: "Search for Research",
    },
  };
}

export default async function SupervisorPage({ params }: PageProps) {
  const { id } = await params;
  if (!AUTHOR_ID.test(id)) notFound();
  const card = await getSupervisor(id);
  if (card === null) notFound();
  // Дата для плашки P-08: дата данных каталога из /health (#16), у индекса без
  // штампа — дата его сборки. Ошибку глотаем — без даты плашка остаётся,
  // страница из-за неё падать не должна.
  const health = await getHealth().catch(() => null);
  const updatedAt = formatIndexDate(catalogueDate(health));

  // Мобильный порядок блоков (шапка → наукометрия → написать → чем занимается →
  // работы → «это вы?») против двух независимых колонок на десктопе: на мобайле
  // обёртки колонок схлопываются в display:contents, порядок задают order-классы.
  return (
    <>
      <ProfileObserver authorId={card.author_id} />
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-[1312px] flex-col gap-4 px-4 pt-[18px] pb-10 sm:gap-6 sm:px-16 sm:pt-7 sm:pb-16">
        <BackToResults />
        <SupervisorHeader card={card} />
        <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_400px] lg:items-start lg:gap-6">
          <div className="contents lg:flex lg:flex-col lg:gap-6">
            <Card className="order-3 flex flex-col gap-2.5 p-[18px] lg:order-none lg:gap-3 lg:px-7 lg:py-[26px]">
              <h2 className="text-[16px] font-semibold lg:text-[18px]">Чем занимается</h2>
              <p className="text-[14px] leading-relaxed text-fg-muted lg:text-[15px]">
                {card.topics.length > 0
                  ? `Ключевые темы по публикациям: ${card.topics.slice(0, 7).map(topicLabel).join("; ")}.`
                  : "Тем в открытых данных не нашлось — загляни в список работ ниже."}
              </p>
              {/* Происхождение тем — внутри блока, а не в футере (P-09):
                  снимает часть юридического риска дешевле, чем что-либо ещё. */}
              <p className="text-[13px] leading-normal text-fg-subtle">
                Темы посчитаны по публикациям в OpenAlex; научный руководитель их не
                подтверждал
              </p>
            </Card>
            <div className="order-4 lg:order-none">
              <WorksList card={card} />
            </div>
          </div>
          <div className="contents lg:flex lg:flex-col lg:gap-5">
            <div className="order-1 lg:order-none">
              <MetricsCard card={card} updatedAt={updatedAt} />
            </div>
            <div className="order-2 lg:order-none">
              <ContactCard card={card} />
            </div>
            <div className="order-5 lg:order-none">
              <ClaimProfileLink authorId={card.author_id} />
            </div>
          </div>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
