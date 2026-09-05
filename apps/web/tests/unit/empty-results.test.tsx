import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyResults, EXAMPLE_QUERIES, QueryHint } from "@/components/empty-results";

describe("EmptyResults", () => {
  it("заголовок, объяснение и три примера удачных запросов", () => {
    render(<EmptyResults onEditQuery={() => {}} onExample={() => {}} />);
    expect(screen.getByText("Уверенных совпадений нет")).toBeInTheDocument();
    expect(EXAMPLE_QUERIES).toHaveLength(3);
    for (const example of EXAMPLE_QUERIES) {
      expect(screen.getByText(example)).toBeInTheDocument();
    }
  });
  it("клик по примеру запускает поиск по нему, кнопка — редактирование", async () => {
    const user = userEvent.setup();
    const onExample = vi.fn();
    const onEditQuery = vi.fn();
    render(<EmptyResults onEditQuery={onEditQuery} onExample={onExample} />);
    await user.click(screen.getByText(EXAMPLE_QUERIES[0]!));
    expect(onExample).toHaveBeenCalledWith(EXAMPLE_QUERIES[0]);
    await user.click(screen.getByRole("button", { name: "Изменить запрос" }));
    expect(onEditQuery).toHaveBeenCalled();
  });
});

describe("QueryHint", () => {
  it("показывает текст 422 как подсказку про запрос, а не как отказ сервиса", async () => {
    const user = userEvent.setup();
    const onEditQuery = vi.fn();
    render(<QueryHint message="Запрос слишком короткий: 2 символа." onEditQuery={onEditQuery} />);
    expect(screen.getByText("Поправь запрос")).toBeInTheDocument();
    expect(screen.getByText("Запрос слишком короткий: 2 символа.")).toBeInTheDocument();
    expect(screen.queryByText("Сервис сейчас недоступен")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Изменить запрос" }));
    expect(onEditQuery).toHaveBeenCalled();
  });
});
