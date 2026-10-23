import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ResponsiveDirectory } from "../components/ResponsiveDirectory";
import { setLocale } from "../lib/i18n";
import { useCompactNavigation } from "../lib/useCompactNavigation";

let width = 768;
let previous: PropertyDescriptor | undefined;
const listeners = new Map<string, Set<() => void>>();

beforeEach(() => {
  setLocale("en");
  width = 768;
  listeners.clear();
  previous = Object.getOwnPropertyDescriptor(window, "matchMedia");
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn((query: string) => {
      const callbacks = listeners.get(query) ?? new Set<() => void>();
      listeners.set(query, callbacks);
      return {
        get matches() {
          return width <= Number(query.match(/\d+/)?.[0]);
        },
        addEventListener: (_: string, update: () => void) => callbacks.add(update),
        removeEventListener: (_: string, update: () => void) => callbacks.delete(update),
      };
    }),
  });
});
afterEach(() => {
  if (previous) Object.defineProperty(window, "matchMedia", previous);
  else Reflect.deleteProperty(window, "matchMedia");
});

function Directory({ selectedKey = "topic-1" }: { selectedKey?: string | null }) {
  const shellCompact = useCompactNavigation();
  return (
    <>
      <span data-testid="shell-layout">{shellCompact ? "compact" : "wide"}</span>
      <ResponsiveDirectory
        selectedKey={selectedKey}
        title="Topic directory"
        summary="1 topic"
        icon={<span aria-hidden="true" />}
        className="knowledge-index"
      >
        {(collapse) => (
          <>
            <input aria-label="Catalogue draft" defaultValue="" />
            <button type="button" onClick={collapse}>
              Select topic
            </button>
          </>
        )}
      </ResponsiveDirectory>
    </>
  );
}

it("collapses a selected directory at 768px without changing the shell or losing an unsent draft", () => {
  render(<Directory />);
  expect(screen.getByTestId("shell-layout")).toHaveTextContent("wide");
  const draft = screen.getByLabelText("Catalogue draft");
  expect(draft).not.toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Expand Topic directory" }));
  fireEvent.change(draft, { target: { value: "EGFR / 未提交" } });
  fireEvent.click(screen.getByRole("button", { name: "Select topic" }));
  expect(draft).not.toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Expand Topic directory" }));
  expect(draft).toBeVisible();
  expect(draft).toHaveValue("EGFR / 未提交");
});

it("leaves an unselected directory reachable at the intermediate width", () => {
  render(<Directory selectedKey={null} />);
  expect(screen.getByLabelText("Catalogue draft")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Expand Topic directory" })).not.toBeInTheDocument();
});

it("responds to narrowing and cleans up both original media subscriptions", () => {
  width = 1024;
  const view = render(<Directory />);
  expect(screen.getByLabelText("Catalogue draft")).toBeVisible();
  act(() => {
    width = 768;
    for (const callbacks of listeners.values()) for (const update of callbacks) update();
  });
  expect(screen.getByLabelText("Catalogue draft")).not.toBeVisible();
  expect(screen.getByTestId("shell-layout")).toHaveTextContent("wide");
  act(() => {
    width = 390;
    for (const callbacks of listeners.values()) for (const update of callbacks) update();
  });
  expect(screen.getByTestId("shell-layout")).toHaveTextContent("compact");
  view.unmount();
  expect([...listeners.values()].every((callbacks) => callbacks.size === 0)).toBe(true);
});
