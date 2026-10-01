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
