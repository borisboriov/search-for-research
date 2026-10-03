import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { VisitObserver } from "@/components/analytics-observer";

// Шрифтовая пара направления B (design/DESIGN_SYSTEM.md §1): сериф Literata
// для всего, что говорит от лица сервиса и для имён НР; гротеск IBM Plex Sans
// для служебного текста и данных. Файлы лежат в репозитории (app/fonts, OFL):
// next/font/google качал их на каждой сборке, и однажды сборка на этом упала
// (#125). Это те же файлы, что раздавал Google Fonts, — вариативные по весу,
// латиница + кириллица + греческий + вьетнамский; собраны и сверены с ним
// глиф в глиф скриптом scripts/build_fonts.py. Используются веса Literata
// 500/600 и Plex 400/500/600.
const literata = localFont({
  src: [{ path: "./fonts/Literata.woff2", weight: "400 900", style: "normal" }],
  variable: "--font-literata",
  display: "swap",
  adjustFontFallback: "Times New Roman",
});

const plex = localFont({
  src: [{ path: "./fonts/IBMPlexSans.woff2", weight: "100 700", style: "normal" }],
  variable: "--font-plex",
  display: "swap",
  adjustFontFallback: "Arial",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: {
    default: "Search for Research — подбор научного руководителя",
    template: "%s | Search for Research",
  },
  description:
    "Кросс-вузовый подбор научных руководителей: опиши интересы своими словами и получи подборку научруков со степенью совпадения и наукометрией.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className={`${literata.variable} ${plex.variable} antialiased`}><VisitObserver />{children}</body>
    </html>
  );
}
