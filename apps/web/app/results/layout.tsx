import type { Metadata } from "next";

// Выдача персональная и эфемерная — поисковикам тут делать нечего (SPEC_SFR3 §2).
export const metadata: Metadata = {
  title: "Результаты подбора",
  robots: { index: false, follow: false },
};

export default function ResultsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
