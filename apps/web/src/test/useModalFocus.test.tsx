import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type ReactNode, useState } from "react";
import { expect, it, vi } from "vitest";

import { useModalFocus } from "../lib/useModalFocus";

function FocusScope({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  const ref = useModalFocus<HTMLElement>(true, onClose);
  return (
    <section ref={ref} role="dialog" aria-modal="true" aria-label={label} tabIndex={-1}>
      {children}
    </section>
  );
}

function NestedDialogHarness() {
  const [outerOpen, setOuterOpen] = useState(false);
  const [innerOpen, setInnerOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOuterOpen(true)}>
        打开外层
      </button>
      {outerOpen ? (
        <FocusScope label="外层" onClose={() => setOuterOpen(false)}>
          <button type="button" data-modal-autofocus="true" onClick={() => setInnerOpen(true)}>
            打开内层
          </button>
          <button type="button" onClick={() => setOuterOpen(false)}>
            关闭外层
          </button>
          {innerOpen ? (
            <FocusScope label="内层" onClose={() => setInnerOpen(false)}>
              <button type="button" data-modal-autofocus="true" onClick={() => setInnerOpen(false)}>
                关闭内层
              </button>
            </FocusScope>
          ) : null}
        </FocusScope>
      ) : null}
    </>
  );
}

it.each([
  {
    name: "collapsed disclosure",
    wrap: (child: ReactNode) => (
      <details>
        <summary>高级选项</summary>
        {child}
      </details>
    ),
  },
  { name: "hidden ancestor", wrap: (child: ReactNode) => <div aria-hidden="true">{child}</div> },
  { name: "display none ancestor", wrap: (child: ReactNode) => <div style={{ display: "none" }}>{child}</div> },
  {
    name: "visibility hidden ancestor",
    wrap: (child: ReactNode) => <div style={{ visibility: "hidden" }}>{child}</div>,
  },
  { name: "disabled fieldset", wrap: (child: ReactNode) => <fieldset disabled>{child}</fieldset> },
])("skips an autofocus request inside $name", async ({ wrap }) => {
  render(
    <FocusScope label="可操作控件" onClose={vi.fn()}>
      <button type="button">首个可用操作</button>
      {wrap(
        <button type="button" data-modal-autofocus="true">
          不可用操作
        </button>,
      )}
    </FocusScope>,
  );
  await waitFor(() => expect(screen.getByRole("button", { name: "首个可用操作" })).toHaveFocus());
});

it("wraps Tab around visible controls instead of a hidden trailing button", async () => {
  render(
    <FocusScope label="可见焦点环" onClose={vi.fn()}>
      <button type="button">第一个</button>
      <button type="button">最后一个</button>
      <div aria-hidden="true">
        <button type="button">隐藏的末尾</button>
      </div>
    </FocusScope>,
  );
  const first = screen.getByRole("button", { name: "第一个" });
  const last = screen.getByRole("button", { name: "最后一个" });
  last.focus();
  fireEvent.keyDown(last, { key: "Tab" });
  expect(first).toHaveFocus();
  fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
  expect(last).toHaveFocus();
});

it.each(["preventDefault", "stopPropagation"] as const)(
  "lets a child consume Escape with %s before dismissing the dialog",
  async (consume) => {
    const onClose = vi.fn();
    render(
      <FocusScope label="输入层级" onClose={onClose}>
        <input aria-label="输入框" onKeyDown={(event) => event[consume]()} />
      </FocusScope>,
    );
    const input = screen.getByRole("textbox", { name: "输入框" });
    await waitFor(() => expect(input).toHaveFocus());
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
    expect(input).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  },
);

it.each([
  { name: "input-method composition", options: { isComposing: true } },
  { name: "held-key repetition", options: { repeat: true } },
])("does not dismiss on Escape during $name", async ({ options }) => {
  const onClose = vi.fn();
  render(
    <FocusScope label="输入保护" onClose={onClose}>
      <input aria-label="输入框" />
    </FocusScope>,
  );
  const input = screen.getByRole("textbox", { name: "输入框" });
  await waitFor(() => expect(input).toHaveFocus());
  fireEvent.keyDown(input, { key: "Escape", ...options });
  expect(onClose).not.toHaveBeenCalled();
  fireEvent.keyDown(input, { key: "Escape" });
  expect(onClose).toHaveBeenCalledOnce();
});

it("makes sibling branches inert while open and restores their original state on unmount", () => {
  const { unmount } = render(
    <>
      <button type="button">背景操作</button>
      <div inert data-testid="already-inert">
        原本禁用的分区
      </div>
      <FocusScope label="交互隔离" onClose={vi.fn()}>
        <button type="button">弹窗操作</button>
      </FocusScope>
    </>,
  );
  const background = screen.getByRole("button", { name: "背景操作" });
  const alreadyInert = screen.getByTestId("already-inert");
  expect(background).toHaveAttribute("inert");
  expect(screen.getByRole("dialog")).not.toHaveAttribute("inert");
  expect(screen.getByRole("button", { name: "弹窗操作" })).not.toHaveAttribute("inert");
  unmount();
  expect(background).not.toHaveAttribute("inert");
  expect(alreadyInert).toHaveAttribute("inert");
});

it("preserves an intentional focus move before the modal autofocus frame runs", () => {
  const frames = new Map<number, FrameRequestCallback>();
  let nextFrame = 0;
  const requestFrame = vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
    const id = ++nextFrame;
    frames.set(id, callback);
    return id;
  });
  const cancelFrame = vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id) => {
    frames.delete(id);
  });
  try {
    render(
      <FocusScope label="导航" onClose={vi.fn()}>
        <button type="button">关闭导航</button>
        <button type="button">目标工作域</button>
      </FocusScope>,
    );
    const destination = screen.getByRole("button", { name: "目标工作域" });
    destination.focus();
    act(() => {
      for (const callback of frames.values()) callback(0);
      frames.clear();
    });
    expect(destination).toHaveFocus();
  } finally {
    requestFrame.mockRestore();
    cancelFrame.mockRestore();
  }
});

it("keeps Escape and focus restoration scoped to the topmost nested modal", async () => {
  render(<NestedDialogHarness />);
  const outerOpener = screen.getByRole("button", { name: "打开外层" });
  outerOpener.focus();
  fireEvent.click(outerOpener);
  const innerOpener = screen.getByRole("button", { name: "打开内层" });
  await waitFor(() => expect(innerOpener).toHaveFocus());

  fireEvent.click(innerOpener);
  await waitFor(() => expect(screen.getByRole("button", { name: "关闭内层" })).toHaveFocus());
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "内层" })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "外层" })).toBeInTheDocument();
  await waitFor(() => expect(innerOpener).toHaveFocus());

  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "外层" })).not.toBeInTheDocument();
  await waitFor(() => expect(outerOpener).toHaveFocus());
});
