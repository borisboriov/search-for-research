import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import { SupervisorHeader } from "@/components/supervisor-header";
import { topicLabel } from "@/lib/topics";
import type { SupervisorCard } from "@/lib/types";

vi.mock("@/components/match-grade", () => ({ MatchGrade: () => null }));
vi.mock("next/link", () => ({
  default: ({ prefetch, ...props }: ComponentProps<"a"> & { prefetch?: boolean }) =>
    <a {...props} data-prefetch={String(prefetch)} />,
}));

const CARD: SupervisorCard = {
  author_id: "A1", name: "Author", institution: null, position: null,
  h_index: null, works_count: 0, topics: ["Topic Modeling", "Unknown / A&B"],
  profile_text: "", cited_by_count: null, email: null, serendipity: false, top_works: [],
};

describe("SupervisorHeader", () => {
  it("показывает русскую подпись, ищет исходную тему и отключает prefetch", () => {
    render(<SupervisorHeader card={CARD} />);
    const topic = screen.getByRole("link", { name: topicLabel("Topic Modeling") });
    expect(topic).toHaveAttribute("href", "/results?q=Topic%20Modeling");
    expect(topic).toHaveAttribute("rel", "nofollow");
    expect(topic).toHaveAttribute("data-prefetch", "false");
  });
  it("неизвестная тема остаётся исходной и безопасно кодируется", () => {
    render(<SupervisorHeader card={CARD} />);
    expect(screen.getByRole("link", { name: "Unknown / A&B" })).toHaveAttribute(
      "href", "/results?q=Unknown%20%2F%20A%26B",
    );
  });
});
