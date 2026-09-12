import { PillLabel } from "@/components/pill-label";
import { SearchBox } from "@/components/search-box";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { SupervisorPreviewCard } from "@/components/supervisor-card";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getHealth, getSupervisor } from "@/lib/api";
import { PREVIEW_AUTHOR_IDS } from "@/lib/preview";
import { cn, formatNumber, pluralize } from "@/lib/utils";
import Link from "next/link";

export const revalidate = 3600; // каталог меняется раз в семестр — час устаревания ничем не грозит

const STEPS = [
  {
    title: "Опиши интересы",
    text: "Своими словами, без формальностей: тема, методы, что нравится. Хватит пары предложений.",
  },
  {
    title: "Получи подборку",
    text: "Топ-10 научруков из разных вузов со степенью совпадения, темами и наукометрией — меньше чем за секунду.",
  },
  {
    title: "Напиши научруку",
    text: "Открой профиль, посмотри последние работы и отправь письмо по готовому шаблону.",
  },
] as const;

// Цифры доверия — Literata 44px цветом `--fg`, не акцентом: правило 2
// направления B (заливок акцентом две на экран, числа акцентом были третьей).
function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col items-center gap-2.5 text-center">
      <span className="font-display text-[28px] leading-none font-semibold tracking-[-0.01em] text-fg sm:text-[44px]">
        {value}
      </span>
      <span className="text-[13px] leading-snug text-fg-muted sm:text-[14px]">{label}</span>
    </div>
  );
}

export default async function LandingPage() {
  // Ошибки API ловим локально: лендинг деградирует (без счётчика и превью),
  // а не отдаёт 500 — статическая часть страницы ценнее счётчика. Цена:
  // ревалидация при упавшем API кэширует деградированную версию на час;
  // после деплоя её чинит пост-деплойная ревалидация (deploy/README.md).
  const [health, ...previewCards] = await Promise.all([
    getHealth().catch(() => null),
    ...PREVIEW_AUTHOR_IDS.map((id) => getSupervisor(id).catch(() => null)),
  ]);
  const preview = previewCards.filter((card) => card !== null);

  return (
    <>
      <SiteHeader variant="landing" />
      <main>
        {/* Hero */}
        <section
          id="search"
          className="flex flex-col items-center gap-[18px] px-4 pt-10 pb-10 sm:gap-6 sm:px-16 sm:pt-[88px] sm:pb-[72px]"
        >
          <PillLabel>Кросс-вузовый подбор научных руководителей</PillLabel>
          <h1 className="max-w-[1100px] text-center font-display text-[42px] leading-[1.04] font-medium tracking-[-0.015em] text-balance sm:text-[76px]">
            Научный руководитель под твою тему — за&nbsp;минуту
          </h1>
          <p className="max-w-[640px] text-center text-[17px] leading-[1.5] text-fg-muted sm:text-[20px]">
            Опиши, что тебе интересно в науке, — и получи подборку научруков из разных вузов
            со степенью совпадения и честной наукометрией.
          </p>
          <div className="w-full sm:max-w-[760px]">
            <SearchBox />
          </div>
        </section>

        {/* Превью подборки: реальные профили каталога, без выдуманных процентов */}
        {preview.length > 0 && (
          <section
            aria-label="Пример подборки"
            className="flex flex-col items-center gap-4 bg-bg-muted px-4 py-12 sm:gap-6 sm:px-16 sm:py-20"
          >
            <PillLabel>Так выглядит подборка</PillLabel>
            <h2 className="max-w-[720px] text-center font-display text-[30px] leading-[1.15] font-semibold text-balance sm:text-[40px]">
              Научруки из разных вузов — по&nbsp;твоему запросу
            </h2>
            <div className="grid w-full grid-cols-1 items-start gap-4 sm:grid-cols-3">
              {preview.map((card, index) => (
                <div key={card.author_id} className={index === 2 ? "hidden sm:block" : undefined}>
                  <SupervisorPreviewCard card={card} />
                </div>
              ))}
            </div>
            <p className="text-center text-[13px] text-fg-subtle">
              Наукометрия — по данным открытого каталога OpenAlex
            </p>
          </section>
        )}

        {/* Три шага */}
        <section
          id="how-it-works"
          className="flex flex-col items-center gap-4 px-4 py-12 sm:gap-6 sm:px-16 sm:py-20"
        >
          <PillLabel>Как это работает</PillLabel>
          <h2 className="text-center font-display text-[30px] leading-[1.15] font-semibold sm:text-[40px]">
            Три шага до научрука
          </h2>
          {/* Кружков «1 / 2 / 3» в v2 нет — порядок несёт сетка, а не третья
              акцентная заливка (S-06, DESIGN_SYSTEM v2 §3). */}
          <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-3">
            {STEPS.map((step) => (
              <Card key={step.title} className="flex flex-col gap-2.5 p-5 sm:p-6">
                <h3 className="text-[16px] font-semibold sm:text-[17px]">{step.title}</h3>
                <p className="text-[14px] leading-[1.5] text-fg-muted sm:text-[15px]">
                  {step.text}
                </p>
              </Card>
            ))}
          </div>
        </section>

        {/* Полоса цифр: живые числа из /api/health, ничего выдуманного */}
        <section
          aria-label="Сервис в цифрах"
          className="grid grid-cols-1 gap-8 bg-bg-muted px-4 py-10 sm:grid-cols-3 sm:px-16 sm:py-14"
        >
          {health && (
            <Stat
              value={formatNumber(health.profiles_count)}
              label={`${pluralize(health.profiles_count, "научрук", "научрука", "научруков")} в каталоге`}
            />
          )}
          {health && (
            <Stat
              value={`${formatNumber(health.institutions_count)} ${pluralize(health.institutions_count, "вуз", "вуза", "вузов")}`}
              label="в каталоге, дальше — больше"
            />
          )}
          <Stat value="100%" label="открытые данные — OpenAlex" />
        </section>

        {/* CTA */}
        <section className="flex flex-col items-center gap-4 bg-accent-deep px-4 py-12 sm:gap-5 sm:px-16 sm:py-20">
          <h2 className="max-w-[720px] text-center font-display text-[30px] leading-[1.15] font-semibold text-balance text-white sm:text-[40px]">
            Поиск научрука — <span className="whitespace-nowrap">3–12 недель.</span> Или минута.
          </h2>
          <p className="max-w-[560px] text-center text-[15px] leading-[1.5] text-accent-deep-fg sm:text-[17px]">
            Не ограничивайся своей кафедрой — выбирай из сотен исследователей разных вузов.
          </p>
          <Link
            href="/#search"
            className={cn(
              buttonVariants({ variant: "inverse" }),
              "focus-visible:outline-white max-sm:w-full",
            )}
          >
            Попробовать бесплатно
          </Link>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
