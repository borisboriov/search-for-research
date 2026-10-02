import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { emitEvent } from "@/lib/analytics";
import { ContactCard } from "@/components/contact-card";
import type { SupervisorCard } from "@/lib/types";

vi.mock("@/lib/analytics", () => ({ emitEvent: vi.fn() }));
beforeEach(() => vi.mocked(emitEvent).mockClear());

const CARD: SupervisorCard = {
  author_id: "A1", name: "Latin Name", institution: null, position: null,
  h_index: null, works_count: 3, topics: [], profile_text: "", cited_by_count: null,
  email: null, serendipity: false,
  top_works: [
    { title: "Old highly cited work", year: 2001 },
    { title: "Without known year", year: null },
    { title: "Recent selected work", year: 2025 },
  ],
};

const draft = () => screen.getByLabelText("Черновик письма");

describe("ContactCard", () => {
  it("предлагает свежую работу, но включает её только после подтверждения", async () => {
    const user = userEvent.setup();
    render(<ContactCard card={CARD} />);
    const select = screen.getByRole("combobox", { name: "Работа для письма" });
    expect(within(select).getByRole("option", { selected: true })).toHaveTextContent("2025 · Recent selected work");
    expect(draft()).not.toHaveTextContent("Recent selected work");
    await user.click(screen.getByRole("checkbox", { name: "Добавить выбранную работу в письмо" }));
    expect(draft()).toHaveTextContent("«Recent selected work» (2025)");
    expect(draft()).not.toHaveTextContent("Old highly cited work");
  });
  it("смена работы требует нового подтверждения; можно написать без неё", async () => {
    const user = userEvent.setup();
    render(<ContactCard card={CARD} />);
    const select = screen.getByRole("combobox");
    const confirm = screen.getByRole("checkbox");
    await user.click(confirm);
    await user.selectOptions(select, "1");
    expect(confirm).not.toBeChecked();
    expect(draft()).not.toHaveTextContent("Old highly cited work");
    await user.click(confirm);
    expect(draft()).toHaveTextContent("«Old highly cited work» (2001)");
    await user.selectOptions(select, "");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(draft()).not.toHaveTextContent("Old highly cited work");
  });
  it("работа без года доступна для выбора и копируется без выдуманного года", async () => {
    const user = userEvent.setup();
    render(<ContactCard card={{ ...CARD, top_works: [CARD.top_works[1]!] }} />);
    expect(screen.getByText(/Годы работ неизвестны/)).toBeInTheDocument();
    expect(screen.getByRole("option", { selected: true })).toHaveTextContent("год не указан");
    await user.click(screen.getByRole("checkbox"));
    expect(draft()).toHaveTextContent("«Without known year» —");
    expect(draft()).not.toHaveTextContent("null");
  });
  it("без работ нет селектора или утверждения о прочитанном; черновик копируется", async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    render(<ContactCard card={{ ...CARD, top_works: [] }} />);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(draft()).not.toHaveTextContent("Прочитал");
    await user.click(screen.getByRole("button", { name: "Скопировать письмо" }));
    expect(writeText).toHaveBeenCalledWith(draft().textContent);
    expect(await screen.findByRole("button", { name: "Скопировано" })).toBeInTheDocument();
    writeText.mockRestore();
  });
  it("копирует именно подтверждённую работу и сохраняет поля студента", async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    render(<ContactCard card={CARD} />);
    await user.selectOptions(screen.getByRole("combobox"), "1");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Скопировать письмо" }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("«Old highly cited work» (2001)"));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("[Имя Отчество]"));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("[какую задачу хочу решать / тема ВКР]"));
    writeText.mockRestore();
  });
  it("переход на другого автора снимает подтверждение", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<ContactCard card={CARD} />);
    await user.click(screen.getByRole("checkbox"));
    rerender(<ContactCard card={{ ...CARD, author_id: "A2" }} />);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(draft()).not.toHaveTextContent("Прочитал");
  });
});


describe("clipboard analytics use resolved outcomes", () => {
  it("address success records outcome without including email or letter text", async () => {
    const user = userEvent.setup(); const write = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    render(<ContactCard card={{ ...CARD, email: "private@example.invalid" }} />);
    await user.click(screen.getByRole("button", { name: "Скопировать" }));
    expect(emitEvent).toHaveBeenCalledWith("address_copy_success", { author_id: CARD.author_id });
    expect(JSON.stringify(vi.mocked(emitEvent).mock.calls)).not.toContain("private@example.invalid"); write.mockRestore();
  });
  it("failed clipboard and failed fallback record address/letter failures", async () => {
    const user = userEvent.setup(); const write = vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
    Object.defineProperty(document, "execCommand", { configurable: true, value: () => false });
    render(<ContactCard card={{ ...CARD, email: "private@example.invalid" }} />);
    await user.click(screen.getByRole("button", { name: "Скопировать" }));
    await user.click(screen.getByRole("button", { name: "Скопировать письмо" }));
    expect(emitEvent).toHaveBeenCalledWith("address_copy_failed", { author_id: CARD.author_id });
    expect(emitEvent).toHaveBeenCalledWith("letter_copy_failed", { author_id: CARD.author_id });
    expect(vi.mocked(emitEvent).mock.calls.some(([name]) => name.endsWith("_success"))).toBe(false); write.mockRestore();
  });
  it("clicking before clipboard acknowledgement does not count as success", async () => {
    const user = userEvent.setup(); let done!: () => void;
    const write = vi.spyOn(navigator.clipboard, "writeText").mockImplementation(() => new Promise<void>(resolve => { done = resolve; }));
    render(<ContactCard card={CARD} />); await user.click(screen.getByRole("button", { name: "Скопировать письмо" }));
    expect(emitEvent).not.toHaveBeenCalled(); done();
    expect(await screen.findByRole("button", { name: "Скопировано" })).toBeInTheDocument();
    expect(emitEvent).toHaveBeenCalledWith("letter_copy_success", { author_id: CARD.author_id }); write.mockRestore();
  });
});
