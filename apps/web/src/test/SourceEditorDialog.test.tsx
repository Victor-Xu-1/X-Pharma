import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { DataSource } from "../lib/contracts/dataFactory";
import { updateDataSource } from "../lib/contracts/dataFactory";
import { setLocale } from "../lib/i18n";
import { SourceEditorDialog } from "../views/dataFactory/SourceEditorDialog";

vi.mock("../lib/contracts/dataFactory", async (original) => ({
  ...(await original<typeof import("../lib/contracts/dataFactory")>()),
  updateDataSource: vi.fn(),
}));

const source: DataSource = {
  id: "controlled-source",
  name: "原始 source <Bio>",
  source_type: "folder",
  root_uri: "/sources/原始文件",
  owner: "原始负责人",
  authorization_scopes: ["SOURCE_SCOPE"],
  authorization_valid_from: "2026-10-09T10:24:59.123456Z",
  authorization_valid_until: "2026-10-09T10:24:59.654321Z",
  data_classification: "internal",
  dataset_key: "Original dataset",
  scan_interval_seconds: 300,
  expected_freshness_seconds: 86400,
  routing_rules: [],
  config_version: 1,
  consecutive_failures: 0,
  credential_configured: false,
  exclude_globs: [],
  include_globs: ["*", "**/*"],
  last_cursor_at: null,
  last_error: null,
  last_scanned_at: null,
  last_success_at: null,
  max_file_bytes: 1073741824,
  rate_limit_per_minute: 60,
  stable_seconds: 30,
  state: "active",
  unavailable_since: null,
};

beforeEach(() => {
  vi.mocked(updateDataSource).mockReset();
});

it("preserves untouched source authorization timestamps, including sub-minute and fractional precision", async () => {
  const accepted = vi.fn(async () => undefined);
  vi.mocked(updateDataSource).mockResolvedValue(source);
  render(
    <SourceEditorDialog
      source={source}
      datasets={[]}
      allowedFolderRoots={[]}
      durableWorkflowsEnabled
      onClose={vi.fn()}
      onCreated={accepted}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /^保存$/ }));
  await waitFor(() => expect(updateDataSource).toHaveBeenCalledOnce());
  expect(updateDataSource).toHaveBeenCalledWith(
    source.id,
    expect.objectContaining({
      authorization_valid_from: source.authorization_valid_from,
      authorization_valid_until: source.authorization_valid_until,
    }),
  );
  await waitFor(() => expect(accepted).toHaveBeenCalledOnce());
});

it("retains original draft values on language changes and disables the complete editor during submission", async () => {
  setLocale("en");
  let release!: () => void;
  vi.mocked(updateDataSource).mockReturnValue(
    new Promise((resolve) => {
      release = () => resolve(source);
    }),
  );
  const accepted = vi.fn(async () => undefined),
    close = vi.fn();
  render(
    <SourceEditorDialog
      source={source}
      datasets={[]}
      allowedFolderRoots={[]}
      durableWorkflowsEnabled
      onClose={close}
      onCreated={accepted}
    />,
  );
  fireEvent.change(screen.getByLabelText("Source name"), { target: { value: "未提交原始草稿" } });
  act(() => setLocale("zh-CN"));
  expect(screen.getByLabelText("数据源名称")).toHaveValue("未提交原始草稿");
  fireEvent.click(screen.getByRole("button", { name: /^保存$/ }));
  expect(screen.getByRole("dialog")).toHaveAttribute("aria-busy", "true");
  expect(screen.getByLabelText("数据源名称")).toBeDisabled();
  expect(screen.getByLabelText("数据负责人")).toBeDisabled();
  expect(screen.getByLabelText("授权范围编号（每行一个）")).toBeDisabled();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(close).not.toHaveBeenCalled();
  act(() => setLocale("en"));
  expect(screen.getByLabelText("Source name")).toHaveValue("未提交原始草稿");
  await act(async () => {
    release();
  });
  expect(accepted).toHaveBeenCalledOnce();
});
