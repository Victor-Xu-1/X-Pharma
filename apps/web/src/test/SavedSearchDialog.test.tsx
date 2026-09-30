import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { SavedSearchDialog } from "../components/SavedSearchDialog";

function DialogHarness() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        保存/订阅
      </button>
      <SavedSearchDialog
        open={open}
        domainLabel="管线"
        name={name}
        shared={false}
        monitor={true}
        pending={false}
        onNameChange={setName}
        onSharedChange={() => undefined}
        onMonitorChange={() => undefined}
        onClose={() => setOpen(false)}
        onSubmit={(event) => event.preventDefault()}
      />
    </>
  );
}

describe("SavedSearchDialog", () => {
  it("traps keyboard focus, closes on Escape and restores the opener", async () => {
    render(<DialogHarness />);
    const opener = screen.getByRole("button", { name: "保存/订阅" });
    opener.focus();
    fireEvent.click(opener);

    const dialog = screen.getByRole("dialog", { name: "保存当前管线检索" });
    const name = within(dialog).getByLabelText("名称");
    const close = within(dialog).getByRole("button", { name: "关闭" });
    const cancel = within(dialog).getByRole("button", { name: "取消" });
    await waitFor(() => expect(name).toHaveFocus());

    close.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(cancel).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("does not dismiss a pending save", async () => {
    const onClose = vi.fn();
    render(
      <SavedSearchDialog
        open
        domainLabel="管线"
        name="EGFR landscape"
        shared={false}
        monitor={true}
        pending
        onNameChange={() => undefined}
        onSharedChange={() => undefined}
        onMonitorChange={() => undefined}
        onClose={onClose}
        onSubmit={(event) => event.preventDefault()}
      />,
    );
    await waitFor(() => expect(screen.getByLabelText("名称")).toHaveFocus());
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });
});
