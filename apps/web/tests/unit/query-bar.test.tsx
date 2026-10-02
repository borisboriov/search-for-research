import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { QueryBar } from "@/components/query-bar";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

describe("QueryBar", () => {
  it("клик по тексту запроса непосредственно включает редактор", async () => {
    const user = userEvent.setup();
    render(<QueryBar query="графовые нейросети" onSubmitQuery={() => {}} />);
    await user.click(screen.getByRole("button", { name: "Редактировать текущий запрос: графовые нейросети" }));
    expect(screen.getByRole("textbox")).toHaveValue("графовые нейросети");
    expect(screen.getByRole("textbox")).toHaveFocus();
  });

  it("показывает текущий запрос", () => {
    render(<QueryBar query="графовые нейросети" onSubmitQuery={() => {}} />);
    expect(screen.getByText("графовые нейросети")).toBeInTheDocument();
  });

  // REVIEW_SFR-6: дублированный sr-only span заставлял скринридер читать
  // подпись кнопки дважды
  it("подпись кнопки — ровно одна", () => {
    render(<QueryBar query="графовые нейросети" onSubmitQuery={() => {}} />);
    expect(screen.getAllByText("Изменить запрос")).toHaveLength(1);
  });

  it("«Изменить запрос» разворачивает редактор с текстом запроса", async () => {
    const user = userEvent.setup();
    render(<QueryBar query="графовые нейросети" onSubmitQuery={() => {}} />);
    await user.click(screen.getByRole("button", { name: /Изменить запрос/ }));
    expect(screen.getByRole("textbox")).toHaveValue("графовые нейросети");
  });

  it("сабмит сохраняет исходный поисковый текст", async () => {
    const user = userEvent.setup();
    const onSubmitQuery = vi.fn();
    render(<QueryBar query="старый" onSubmitQuery={onSubmitQuery} />);
    await user.click(screen.getByRole("button", { name: /Изменить запрос/ }));
    const textarea = screen.getByRole("textbox");
    await user.clear(textarea);
    await user.type(textarea, "  сверхпроводимость  ");
    await user.click(screen.getByRole("button", { name: "Подобрать научрука" }));
    expect(onSubmitQuery).toHaveBeenCalledWith("  сверхпроводимость  ");
  });

  it("слишком короткий запрос не уходит — показывается ошибка", async () => {
    const user = userEvent.setup();
    const onSubmitQuery = vi.fn();
    render(<QueryBar query="старый" onSubmitQuery={onSubmitQuery} />);
    await user.click(screen.getByRole("button", { name: /Изменить запрос/ }));
    const textarea = screen.getByRole("textbox");
    await user.clear(textarea);
    await user.type(textarea, "ик");
    await user.click(screen.getByRole("button", { name: "Подобрать научрука" }));
    expect(onSubmitQuery).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
