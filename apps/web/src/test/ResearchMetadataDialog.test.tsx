import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ResearchMetadataDialog } from "../components/ResearchMetadataDialog";

const props = {
  title: "编辑研究资料",
  open: true,
  name: "EGFR research",
  description: "Reviewed research scope",
  error: "",
  onNameChange: vi.fn(),
  onDescriptionChange: vi.fn(),
  onClose: vi.fn(),
  onSubmit: vi.fn(),
};

it("keeps research metadata immutable and explains a pending save within the dialog", async () => {
  render(<ResearchMetadataDialog {...props} pending />);
  expect(screen.getByRole("textbox", { name: "名称" })).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "业务说明" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "关闭" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
  expect(screen.getByRole("dialog")).toHaveAttribute("aria-busy", "true");
  expect(screen.getByRole("status")).toHaveTextContent("正在保存研究信息");
  await waitFor(() => expect(screen.getByRole("dialog")).toHaveFocus());
  fireEvent.keyDown(document, { key: "Escape" });
  expect(props.onClose).not.toHaveBeenCalled();
});

it("does not submit research metadata again during an in-flight save", () => {
  const onSubmit = vi.fn();
  render(<ResearchMetadataDialog {...props} onSubmit={onSubmit} pending />);
  fireEvent.submit(screen.getByRole("dialog"));
  expect(onSubmit).not.toHaveBeenCalled();
});

it("re-enables the original fields after rejection and displays the caller's error literally", () => {
  const { rerender } = render(<ResearchMetadataDialog {...props} pending />);
  rerender(<ResearchMetadataDialog {...props} pending={false} error="拒绝保存 <script>" />);
  expect(screen.getByRole("textbox", { name: "名称" })).toHaveValue("EGFR research");
  expect(screen.getByRole("textbox", { name: "业务说明" })).toHaveValue("Reviewed research scope");
  expect(screen.getByRole("textbox", { name: "名称" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "保存修改" })).toBeEnabled();
  expect(screen.getAllByRole("alert")).toHaveLength(1);
  expect(screen.getByRole("alert")).toHaveTextContent("拒绝保存 <script>");
  expect(document.querySelector("script")).toBeNull();
});
