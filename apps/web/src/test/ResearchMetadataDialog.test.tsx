import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ResearchMetadataDialog } from "../components/ResearchMetadataDialog";
import { setLocale } from "../lib/i18n";

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

it("updates shared metadata controls while keeping pending state and source values literal", () => {
  setLocale("en");
  const { rerender } = render(<ResearchMetadataDialog {...props} pending error="原始诊断 <script>" />);
  expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(props.name);
  expect(screen.getByRole("textbox", { name: "Research description" })).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("Saving research information");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("textbox", { name: "名称" })).toHaveValue(props.name);
  expect(screen.getByRole("textbox", { name: "业务说明" })).toHaveValue(props.description);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  rerender(<ResearchMetadataDialog {...props} pending={false} error="原始诊断 <script>" />);
  expect(screen.getByRole("alert")).toHaveTextContent("原始诊断 <script>");
});

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
