import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { expect, it, vi } from "vitest";

import { FacetMultiSelect } from "../components/FacetMultiSelect";
import { useModalFocus } from "../lib/useModalFocus";

function SelectionHarness() {
  const [selected, setSelected] = useState<string[]>([]);
  return (
    <>
      <FacetMultiSelect
        label="临床分期"
        options={[
          { value: "phase1", label: "I 期", count: 8 },
          { value: "phase2", label: "II 期", count: 5 },
        ]}
        selected={selected}
        onChange={setSelected}
      />
      <button type="button">其他操作</button>
    </>
  );
}

async function openSelection() {
  const summary = screen.getByLabelText(/^临床分期：/);
  fireEvent.click(summary);
  const details = summary.closest("details") as HTMLDetailsElement;
  await waitFor(() => expect(details.open).toBe(true));
  return { details, summary };
}

it("dismisses a facet popover with Escape without clearing its selection", async () => {
  render(<SelectionHarness />);
  const { details, summary } = await openSelection();
  const phase = screen.getByRole("checkbox", { name: "I 期8" });
  fireEvent.click(phase);
  phase.focus();
  fireEvent.keyDown(phase, { key: "Escape" });
  expect(details.open).toBe(false);
  expect(summary).toHaveFocus();
  expect(summary).toHaveAttribute("aria-label", "临床分期：I 期");
  fireEvent.click(summary);
  expect(screen.getByRole("checkbox", { name: "I 期8" })).toBeChecked();
});

it.each(["pointer", "focus"] as const)("dismisses on outside %s without stealing focus", async (action) => {
  render(<SelectionHarness />);
  const { details, summary } = await openSelection();
  const phase = screen.getByRole("checkbox", { name: "I 期8" });
  phase.focus();
  fireEvent.pointerDown(phase);
  expect(details.open).toBe(true);
  const outside = screen.getByRole("button", { name: "其他操作" });
  if (action === "pointer") fireEvent.pointerDown(outside);
  else outside.focus();
  expect(details.open).toBe(false);
  expect(summary).not.toHaveFocus();
  if (action === "focus") expect(outside).toHaveFocus();
});

it("consumes facet Escape before the containing modal and leaves the next Escape to the modal", async () => {
  const onClose = vi.fn();
  function ModalHarness() {
    const ref = useModalFocus<HTMLElement>(true, onClose);
    return (
      <section role="dialog" aria-label="高级筛选" aria-modal="true" ref={ref} tabIndex={-1}>
        <SelectionHarness />
      </section>
    );
  }
  render(<ModalHarness />);
  const { details, summary } = await openSelection();
  const phase = screen.getByRole("checkbox", { name: "I 期8" });
  phase.focus();
  fireEvent.keyDown(phase, { key: "Escape" });
  expect(details.open).toBe(false);
  expect(onClose).not.toHaveBeenCalled();
  expect(summary).toHaveFocus();
  fireEvent.keyDown(summary, { key: "Escape" });
  expect(onClose).toHaveBeenCalledOnce();
});
