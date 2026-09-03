import Link from "next/link";

import { LogoMark } from "@/components/logo";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { Card } from "@/components/ui/card";

export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-[1312px] grow px-5 pt-5 pb-10 sm:px-16 sm:pt-9 sm:pb-14">
        <Card className="flex flex-col items-center gap-[18px] rounded-search px-5 py-10 sm:px-12 sm:py-14">
          <span className="flex size-16 items-center justify-center rounded-full bg-accent-soft">
            <LogoMark className="size-[30px] text-fg-subtle" />
          </span>
          <h1 className="text-center font-display text-[24px] font-semibold sm:text-[28px]">
            Такой страницы нет
          </h1>
          <p className="max-w-[560px] text-center text-[15px] leading-relaxed text-fg-muted sm:text-[16px]">
            Профиль мог быть скрыт или адрес набран с ошибкой. Начни с поиска — он знает всех.
          </p>
          <Link
            href="/"
            className="mt-1.5 rounded-btn bg-accent px-[26px] py-3.5 text-[16px] font-medium text-white hover:bg-accent-hover"
          >
            На главную
          </Link>
        </Card>
      </main>
      <SiteFooter />
    </>
  );
}
