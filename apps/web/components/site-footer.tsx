import { Logo } from "@/components/logo";

// В макете в футере есть «О проекте / Научрукам / Контакты» — в MVP этих страниц
// нет, мёртвые псевдоссылки убраны (расхождение зафиксировано в SFR3_REPORT).
export function SiteFooter({ bordered = true }: { bordered?: boolean }) {
  return (
    <footer
      className={`flex flex-col gap-3 px-5 py-7 sm:flex-row sm:items-center sm:justify-between sm:px-16 sm:py-8 ${bordered ? "border-t border-border" : ""}`}
    >
      <Logo mono />
      <div className="text-[13px] text-fg-subtle">Данные: OpenAlex (CC0)</div>
    </footer>
  );
}
