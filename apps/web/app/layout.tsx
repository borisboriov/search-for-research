import type { Metadata } from "next";
import { IBM_Plex_Sans, Literata } from "next/font/google";
import "./globals.css";

// Шрифтовая пара направления B (design/DESIGN_SYSTEM.md §1): сериф Literata
// для всего, что говорит от лица сервиса и для имён НР; гротеск IBM Plex Sans
// для служебного текста и данных. Оба — с кириллицей, self-hosted next/font.
const literata = Literata({
  subsets: ["latin", "cyrillic"],
  weight: ["500", "600"],
  variable: "--font-literata",
  display: "swap",
});

const plex = IBM_Plex_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600"],
  variable: "--font-plex",
  display: "swap",
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
      <body className={`${literata.variable} ${plex.variable} antialiased`}>{children}</body>
    </html>
  );
}
