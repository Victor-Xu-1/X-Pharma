import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type ReactNode, useState } from "react";
import { expect, it } from "vitest";

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
