import type { Metadata } from "next";

import { StatesShowcase } from "@/components/states-showcase";

// Витрина состояний компонентов (skeleton, serendipity, empty, error): API пока
// не выставляет флаг serendipity, поэтому глазами это состояние видно только
// здесь и в тестах (SPEC_SFR3 §2). Не индексируется и закрыта в robots.txt.
export const metadata: Metadata = {
  title: "Состояния компонентов (dev)",
  robots: { index: false, follow: false },
};

export default function StatesPage() {
  return <StatesShowcase />;
}
