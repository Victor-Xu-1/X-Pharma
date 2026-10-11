import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { revealFocusedPipelineControl } from "../views/target/pipeline/focusVisibility";

afterEach(() => vi.restoreAllMocks());

function fixture(top: number, feedback: boolean) {
  render(
    <div className="workspace-main">
      <header className="topbar" />
      <div data-testid="pipeline">
        <fieldset className="target-evidence-filters">
          <input aria-label="Pipeline query" />
        </fieldset>
        {feedback ? <section className="target-pipeline-feedback" /> : null}
      </div>
      <input aria-label="Other view" />
    </div>,
  );
  const root = screen.getByTestId("pipeline"),
    input = screen.getByRole("textbox", { name: "Pipeline query" });
  let inputTop = top;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const y = this === input ? inputTop : this.className === "topbar" ? 0 : 72;
    const height = this === input ? 44 : this.className === "topbar" ? 64 : 128;
    return { top: y, bottom: y + height, left: 15, right: 305, width: 290, height, x: 15, y, toJSON() {} };
  });
  const scroll = vi.spyOn(window, "scrollBy").mockImplementation((options: ScrollToOptions | number) => {
    if (typeof options !== "object") throw new Error("An explicit bounded scroll delta is required");
    inputTop -= options.top ?? 0;
  });
  input.focus();
  return { root, input, scroll };
}

it("reveals a partially visible field below the actual sticky header without changing focus", () => {
  const { root, input, scroll } = fixture(20, false);
  revealFocusedPipelineControl(root);
  expect(scroll).toHaveBeenCalledExactlyOnceWith({ top: -52, behavior: "instant" });
  expect(input).toHaveFocus();
});

it("reserves only the measured feedback height for a genuinely obscured field", () => {
  const { root, input, scroll } = fixture(80, true);
  revealFocusedPipelineControl(root);
  expect(scroll).toHaveBeenCalledExactlyOnceWith({ top: -128, behavior: "instant" });
  expect(input).toHaveFocus();
});

it("does not move an already visible field", () => {
  const { root, input, scroll } = fixture(250, true);
  revealFocusedPipelineControl(root);
  expect(scroll).not.toHaveBeenCalled();
  expect(input).toHaveFocus();
});

it("does not move a field or focus belonging to another view", () => {
  const { root, scroll } = fixture(20, true);
  const other = screen.getByRole("textbox", { name: "Other view" });
  other.focus();
  revealFocusedPipelineControl(root);
  expect(scroll).not.toHaveBeenCalled();
  expect(other).toHaveFocus();
});
