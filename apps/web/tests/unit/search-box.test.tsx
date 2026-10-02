import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SearchBox, validateQuery } from "@/components/search-box";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

describe("SearchBox — лимит интерфейса", () => {
  it.each([499, 500])("разрешает отправку %i символов", async (length) => {
    const onSubmitQuery = vi.fn();
    render(<SearchBox initialQuery={"я".repeat(length)} onSubmitQuery={onSubmitQuery} />);
    expect(screen.getByText(`${length} / 500`)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Подобрать научрука" }));
    expect(onSubmitQuery).toHaveBeenCalledWith("я".repeat(length));
    expect(validateQuery("я".repeat(length))).toBeNull();
  });

  it("501 символ: сохраняет текст, показывает превышение и блокирует даже submit формы", () => {
    const onSubmitQuery = vi.fn();
    const { container } = render(<SearchBox initialQuery={"я".repeat(501)} onSubmitQuery={onSubmitQuery} />);
    expect(screen.getByRole("textbox")).toHaveValue("я".repeat(501));
    expect(screen.getByRole("button", { name: "Подобрать научрука" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Убери 1 символ: максимум 500.");
    fireEvent.submit(container.querySelector("form")!);
    expect(onSubmitQuery).not.toHaveBeenCalled();
  });

  it("длинная вставка полностью сохранена и после сокращения отправляется", async () => {
    const user = userEvent.setup();
    const onSubmitQuery = vi.fn();
    render(<SearchBox onSubmitQuery={onSubmitQuery} />);
    const textarea = screen.getByRole("textbox");
    expect(screen.getByText("0 / 500")).toBeInTheDocument();
    await user.click(textarea);
    await user.paste("я".repeat(1400));
    expect(textarea).toHaveValue("я".repeat(1400));
    expect(textarea).not.toHaveAttribute("maxlength");
    expect(screen.getByText("1400 / 500")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Убери 900 символов");
    fireEvent.change(textarea, { target: { value: "я" } });
    expect(screen.getByText("1 / 500")).toBeInTheDocument();
    fireEvent.change(textarea, { target: { value: "научная тема" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Подобрать научрука" }));
    expect(onSubmitQuery).toHaveBeenCalledWith("научная тема");
  });

  it("счётчик и лимит считают полный текст, включая пробелы", () => {
    render(<SearchBox initialQuery={" " + "я".repeat(500)} />);
    expect(screen.getByText("501 / 500")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Подобрать научрука" })).toBeDisabled();
  });

  it("счётчик считает символы Unicode, а не кодовые единицы UTF-16", () => {
    render(<SearchBox initialQuery={"😀".repeat(500)} />);
    expect(screen.getByText("500 / 500")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Подобрать научрука" })).toBeEnabled();
    expect(validateQuery("😀".repeat(501))).toMatch(/Убери 1 символ:/);
  });
});
