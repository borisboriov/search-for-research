import { Logo } from "@/components/logo";

// В макете в футере есть «О проекте / Научрукам / Контакты» — в MVP этих страниц
// нет, мёртвые псевдоссылки убраны (расхождение зафиксировано в SFR3_REPORT).
// В макете B футер везде с верхней линией — прежний флаг `bordered` не нужен.
export function SiteFooter() {
  return (
    <footer className="flex flex-col gap-3 border-t border-border px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-16 sm:pt-6 sm:pb-8">
      <Logo mono />
      <div className="text-[13px] text-fg-subtle">Данные: OpenAlex (CC0)</div>
    </footer>
  );
}
