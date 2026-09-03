import { describe, expect, it } from "vitest";

import { abstractFragments } from "@/components/works-list";

describe("abstractFragments", () => {
  it("достаёт фрагменты аннотаций из строк profile_text", () => {
    const text = [
      "Ivan Smirnov — МФТИ. h-index: 13.",
      "Ключевые темы: NLP; Topic Modeling.",
      "«Depression detection» (2023). We study social media posts…",
      "«Без аннотации» (2021).",
    ].join("\n");
    const fragments = abstractFragments(text);
    expect(fragments.get("Depression detection")).toBe("We study social media posts…");
    expect(fragments.has("Без аннотации")).toBe(false);
  });
});
