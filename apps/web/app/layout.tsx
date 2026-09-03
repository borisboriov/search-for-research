import type { Metadata } from "next";
import { Golos_Text, Spectral } from "next/font/google";
import "./globals.css";

const spectral = Spectral({
  subsets: ["latin", "cyrillic"],
  weight: ["500", "600"],
  variable: "--font-spectral",
  display: "swap",
});

const golos = Golos_Text({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600"],
  variable: "--font-golos",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: {
    default: "Search for Research — подбор научного руководителя",
    template: "%s | Search for Research",
  },
  description:
    "Кросс-вузовый подбор научных руководителей: опиши интересы своими словами и получи подборку научруков с процентом совпадения и наукометрией.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className={`${spectral.variable} ${golos.variable} antialiased`}>{children}</body>
    </html>
  );
}
