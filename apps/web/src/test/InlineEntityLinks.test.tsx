import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { InlineEntityLinks } from "../components/InlineEntityLinks";

const items = [
  { key: "first", label: "HER2-Positive Breast Carcinoma", id: "disease-1" },
  { key: "second", label: "Hormone Receptor-Positive Breast Carcinoma", id: "disease-2" },
  { key: "third", label: "OSIMERTINIB", id: "drug-1" },
  { key: "fourth", label: "Fourth governed association", id: "entity-4" },
];

it("keeps a readable primary label and exposes every supplied association without truncating the collection", async () => {
  const select = vi.fn();
  render(<InlineEntityLinks label="NCT01234567 关联实体" items={items} onSelect={select} />);
  expect(screen.getByRole("button", { name: items[0].label })).toHaveAttribute("title", items[0].label);
  const more = screen.getByRole("button", { name: "查看 NCT01234567 关联实体（4 项）" });
  more.focus();
  fireEvent.click(more);
  const dialog = screen.getByRole("dialog", { name: "NCT01234567 关联实体" });
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "关闭关联列表" })).toHaveFocus());
  for (const item of items) expect(within(dialog).getByRole("button", { name: item.label })).toBeVisible();
  fireEvent.click(within(dialog).getByRole("button", { name: items[3].label }));
  expect(select).toHaveBeenCalledExactlyOnceWith(items[3]);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("restores keyboard focus on Escape without navigating or selecting an entity", async () => {
  const select = vi.fn();
  render(<InlineEntityLinks label="试验药物" items={items} onSelect={select} />);
  const more = screen.getByRole("button", { name: "查看 试验药物（4 项）" });
  more.focus();
  fireEvent.click(more);
  fireEvent.keyDown(document, { key: "Escape" });
  expect(select).not.toHaveBeenCalled();
  await waitFor(() => expect(more).toHaveFocus());
});

it("renders no fake association or disclosure for zero or one supplied record", () => {
  const select = vi.fn();
  const { rerender } = render(<InlineEntityLinks label="关联实体" items={[]} onSelect={select} />);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  rerender(<InlineEntityLinks label="关联实体" items={items.slice(0, 1)} onSelect={select} />);
  expect(screen.getAllByRole("button")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: items[0].label }));
  expect(select).toHaveBeenCalledExactlyOnceWith(items[0]);
});

it("closes stale relation choices when the authorized collection becomes empty", () => {
  const select = vi.fn();
  const { rerender } = render(<InlineEntityLinks label="关联实体" items={items} onSelect={select} />);
  fireEvent.click(screen.getByRole("button", { name: "查看 关联实体（4 项）" }));
  rerender(<InlineEntityLinks label="关联实体" items={[]} onSelect={select} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  rerender(<InlineEntityLinks label="关联实体" items={items} onSelect={select} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(select).not.toHaveBeenCalled();
});
