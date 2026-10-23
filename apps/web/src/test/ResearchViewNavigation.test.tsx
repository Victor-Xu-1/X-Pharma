import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ResearchViewNavigation } from "../components/ResearchViewNavigation";
import { setLocale } from "../lib/i18n";

function mockBounds(position: { left: number }) {
  return vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const rail = this.tagName === "NAV";
    const left = rail ? 100 : position.left;
    const width = rail ? 200 : 120;
    return { left, right: left + width, top: 1000, bottom: 1048, width, height: 48, x: left, y: 1000, toJSON() {} };
  });
}

it("reveals a deep-linked destination horizontally without changing focus or invoking navigation", () => {
  mockBounds({ left: 400 });
  const onView = vi.fn();
  const focused = document.activeElement;
  render(<ResearchViewNavigation activeView="epidemiology" onView={onView} />);
  const rail = screen.getByRole("navigation", { name: "研发数据分类" });
  expect(rail.scrollLeft).toBe(220);
  expect(document.activeElement).toBe(focused);
  expect(onView).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "流行病学" })).toHaveAttribute("aria-current", "page");
});

it("realigns translated labels without changing the selected destination", () => {
  const position = { left: 120 };
  mockBounds(position);
  const onView = vi.fn();
  render(<ResearchViewNavigation activeView="knowledge" onView={onView} />);
  const rail = screen.getByRole("navigation", { name: "我的研究分类" });
  expect(rail.scrollLeft).toBe(0);
  position.left = 400;
  act(() => setLocale("en"));
  expect(rail.scrollLeft).toBe(220);
  expect(screen.getByRole("button", { name: "Knowledge topics" })).toHaveAttribute("aria-current", "page");
  expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  expect(onView).not.toHaveBeenCalled();
});

it("realigns after a width change and releases the observer on unmount", () => {
  const position = { left: 120 };
  mockBounds(position);
  let resized: ResizeObserverCallback | undefined;
  const observe = vi.fn();
  const disconnect = vi.fn();
  vi.stubGlobal(
    "ResizeObserver",
    class {
      constructor(callback: ResizeObserverCallback) {
        resized = callback;
      }
      observe = observe;
      disconnect = disconnect;
    },
  );
  try {
    const onView = vi.fn();
    const view = render(<ResearchViewNavigation activeView="knowledge" onView={onView} />);
    const rail = screen.getByRole("navigation", { name: "我的研究分类" });
    const selected = screen.getByRole("button", { name: "知识专题" });
    expect(observe).toHaveBeenCalledWith(rail);
    expect(observe).toHaveBeenCalledWith(selected);
    const focused = document.activeElement;
    rail.scrollLeft = 200;
    position.left = -50;
    act(() => resized?.([], {} as ResizeObserver));
    expect(rail.scrollLeft).toBe(50);
    expect(document.activeElement).toBe(focused);
    expect(onView).not.toHaveBeenCalled();
    view.unmount();
    expect(disconnect).toHaveBeenCalledOnce();
  } finally {
    vi.unstubAllGlobals();
  }
});
