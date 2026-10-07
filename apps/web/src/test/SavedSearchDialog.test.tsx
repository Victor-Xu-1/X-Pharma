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
        error=""
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
        error=""
        onNameChange={() => undefined}
        onSharedChange={() => undefined}
        onMonitorChange={() => undefined}
        onClose={onClose}
        onSubmit={(event) => event.preventDefault()}
      />,
    );
    expect(screen.getByLabelText("名称")).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "企业内共享该检索" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "同时订阅相关数据变更" })).toBeDisabled();
    await waitFor(() => expect(screen.getByRole("dialog")).toHaveFocus());
    expect(screen.getByRole("status")).toHaveTextContent("正在保存检索");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("does not submit a second in-flight save from the form", () => {
    const onSubmit = vi.fn();
    render(
      <SavedSearchDialog
        open
        domainLabel="临床"
        name="Reviewed query"
        shared
        monitor
        pending
        error=""
        onNameChange={vi.fn()}
        onSharedChange={vi.fn()}
        onMonitorChange={vi.fn()}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.submit(screen.getByRole("dialog"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("keeps caller-owned values and one error on rejection without forcing subscription", () => {
    render(
      <SavedSearchDialog
        open
        domainLabel="临床"
        name="Reviewed query"
        shared
        monitor={false}
        pending={false}
        error="保存被拒绝 <script>"
        onNameChange={vi.fn()}
        onSharedChange={vi.fn()}
        onMonitorChange={vi.fn()}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("名称")).toHaveValue("Reviewed query");
    expect(screen.getByLabelText("名称")).toBeEnabled();
    expect(screen.getByRole("checkbox", { name: "企业内共享该检索" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "同时订阅相关数据变更" })).not.toBeChecked();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByRole("alert")).toHaveTextContent("保存被拒绝 <script>");
    expect(document.querySelector("script")).toBeNull();
  });
});
