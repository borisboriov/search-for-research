import { SearchBox } from "@/components/search-box";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { SupervisorPreviewCard } from "@/components/supervisor-card";
import { Card } from "@/components/ui/card";
import { getHealth, getSupervisor } from "@/lib/api";
import { PREVIEW_AUTHOR_IDS } from "@/lib/preview";
import { formatNumber, pluralize } from "@/lib/utils";
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

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col gap-1 sm:items-center sm:gap-1.5">
      <span className="font-display text-[26px] font-semibold text-accent sm:text-[40px]">
        {value}
      </span>
      <span className="text-[12px] text-fg-muted sm:text-[15px]">{label}</span>
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
          className="flex flex-col gap-[18px] px-5 pt-9 pb-8 sm:items-center sm:gap-6 sm:px-16 sm:pt-16 sm:pb-14"
        >
          <p className="self-start rounded-full bg-accent-soft px-3 py-1.5 text-[11px] font-medium tracking-[0.06em] text-accent uppercase sm:self-auto sm:px-3.5 sm:py-[7px] sm:text-[13px]">
            Кросс-вузовый подбор научных руководителей
          </p>
          <h1 className="max-w-[820px] font-display text-[34px] leading-[1.15] font-semibold tracking-[-0.01em] sm:text-center sm:text-[54px] sm:leading-[1.12]">
            Научный руководитель под твою тему — за минуту
          </h1>
          <p className="max-w-[640px] text-[16px] leading-normal text-fg-muted sm:text-center sm:text-[19px]">
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
            className="flex flex-col gap-3 px-5 pb-9 sm:gap-5 sm:px-16 sm:pb-[72px]"
          >
            <p className="text-[12px] font-medium tracking-[0.08em] text-fg-subtle uppercase sm:text-center sm:text-[13px]">
              Так выглядит подборка
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-5">
              {preview.map((card, index) => (
                <div key={card.author_id} className={index === 2 ? "hidden sm:block" : undefined}>
                  <SupervisorPreviewCard card={card} />
                </div>
              ))}
            </div>
            <p className="text-[12px] text-fg-subtle sm:text-center sm:text-[13px]">
              Наукометрия — по данным открытого каталога OpenAlex
            </p>
          </section>
        )}

        {/* Три шага */}
        <section
          id="how-it-works"
          className="flex flex-col gap-4 bg-bg-muted px-5 py-10 sm:gap-9 sm:px-16 sm:py-[72px]"
        >
          <h2 className="font-display text-[28px] font-semibold sm:text-center sm:text-[36px]">
            Три шага до научрука
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-6">
            {STEPS.map((step, index) => (
              <Card key={step.title} className="flex gap-3.5 p-5 sm:flex-col sm:p-7">
                <span
                  aria-hidden
                  className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-[15px] font-semibold text-white sm:size-9 sm:text-[16px]"
                >
                  {index + 1}
                </span>
                <span className="flex flex-col gap-1.5 sm:gap-3.5">
                  <h3 className="text-[16px] font-semibold sm:text-[18px]">{step.title}</h3>
                  <p className="text-[14px] leading-normal text-fg-muted sm:text-[15px] sm:leading-relaxed">
                    {step.text}
                  </p>
                </span>
              </Card>
            ))}
          </div>
        </section>

        {/* Полоса цифр: живые числа из /api/health, ничего выдуманного */}
        <section
          aria-label="Сервис в цифрах"
          className="grid grid-cols-3 gap-3 px-5 py-9 sm:flex sm:justify-center sm:gap-24 sm:px-16 sm:py-16"
        >
          {health && (
            <Stat
              value={formatNumber(health.profiles_count)}
              label={`${pluralize(health.profiles_count, "научрук", "научрука", "научруков")} в каталоге`}
            />
          )}
          <Stat value="2 вуза" label="на старте: МФТИ и МГУ, дальше — больше" />
          <Stat value="100%" label="открытые данные — OpenAlex" />
        </section>

        {/* CTA */}
        <section className="flex flex-col gap-4 bg-accent-deep px-5 py-11 sm:items-center sm:gap-[22px] sm:px-16 sm:py-[72px]">
          <h2 className="max-w-[700px] font-display text-[28px] leading-tight font-semibold text-white sm:text-center sm:text-[38px]">
            Поиск научрука — 3–12 недель. Или минута.
          </h2>
          <p className="max-w-[560px] text-[15px] leading-normal text-accent-deep-fg sm:text-center sm:text-[17px]">
            Не ограничивайся своей кафедрой — выбирай из сотен исследователей разных вузов.
          </p>
          <Link
            href="/#search"
            className="rounded-btn bg-surface px-7 py-3.5 text-center text-[16px] font-semibold text-accent-deep hover:bg-accent-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            Попробовать бесплатно
          </Link>
        </section>
      </main>
      <SiteFooter bordered={false} />
    </>
  );
}
