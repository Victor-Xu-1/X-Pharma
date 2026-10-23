import { fireEvent, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ResultPagination } from "../components/ResultPagination";
import { renderWithQueryClient } from "./renderWithQueryClient";

function mockNarrowPageRail() {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const rail = this.tagName === "FIELDSET";
    const left = rail ? 100 : 400;
    const width = rail ? 80 : 44;
    return { left, right: left + width, top: 1000, bottom: 1044, width, height: 44, x: left, y: 1000, toJSON() {} };
  });
}

it("reveals the current page on a narrow rail without issuing a new page request", () => {
  mockNarrowPageRail();
  const onPageChange = vi.fn();
  renderWithQueryClient(<ResultPagination totalRows={1255} offset={600} pageSize={50} onPageChange={onPageChange} />);
  expect(screen.getByRole("group", { name: "页码" }).scrollLeft).toBe(264);
  expect(screen.getByRole("button", { name: "第 13 页" })).toHaveAttribute("aria-current", "page");
  expect(onPageChange).not.toHaveBeenCalled();
});

it("fully reveals a focused page number without selecting it or losing the jump draft", () => {
  mockNarrowPageRail();
  const onPageChange = vi.fn();
  renderWithQueryClient(<ResultPagination totalRows={1255} offset={0} pageSize={50} onPageChange={onPageChange} />);
  const rail = screen.getByRole("group", { name: "页码" });
  fireEvent.change(screen.getByLabelText("目标页码"), { target: { value: "12" } });
  rail.scrollLeft = 0;
  fireEvent.focus(screen.getByRole("button", { name: "第 26 页" }));
  expect(rail.scrollLeft).toBe(264);
  expect(screen.getByLabelText("目标页码")).toHaveValue(12);
  expect(screen.getByRole("button", { name: "第 1 页" })).toHaveAttribute("aria-current", "page");
  expect(onPageChange).not.toHaveBeenCalled();
});
