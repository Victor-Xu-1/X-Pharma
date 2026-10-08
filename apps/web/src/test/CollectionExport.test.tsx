import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import {
  type CollectionDetail,
  type CollectionPolicy,
  collectionsKeys,
  exportComparisonSet,
  getWorkspaceExportPolicy,
} from "../lib/contracts/collections";
import { downloadBlob } from "../lib/download";
import { CollectionExport } from "../views/collections/CollectionExport";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/collections", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/contracts/collections")>()),
  getWorkspaceExportPolicy: vi.fn(),
  exportComparisonSet: vi.fn(),
}));
vi.mock("../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/download")>()),
  downloadBlob: vi.fn(),
}));
const detail: CollectionDetail = {
  id: "11111111-1111-4111-8111-111111111111",
  owner_user_id: "owner",
  name: "Research list",
  description: "",
  visibility: "private",
  version: 2,
  member_count: 1,
  editable: true,
  members: [],
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
};
const policy: CollectionPolicy = {
  id: "policy",
  policy_version: "workspace-export-v1",
  enabled: true,
  allowed_formats: ["json", "xlsx"],
  allowed_fields: ["position", "id", "entity_type", "name", "description"],
  max_records_per_export: 20,
  attribution: "Controlled test fixture",
  configured_by_user_id: "owner",
  policy_sha256: "a".repeat(64),
  created_at: detail.created_at,
  updated_at: detail.updated_at,
};

beforeEach(() => {
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(policy);
  vi.mocked(exportComparisonSet).mockResolvedValue(new Blob(["{}"]));
});

// The legacy control is permanently expanded; exercise the same operation there
// while the new control explicitly opens its native progressive disclosure.
async function openExport() {
  const summary = screen.queryByText("导出列表", { selector: "summary" });
  if (summary) {
    const details = summary.closest("details");
    if (!details) throw new Error("Export disclosure missing");
    details.open = true;
    fireEvent(details, new Event("toggle"));
  }
}

it("reads export policy only when the researcher opens the control", async () => {
  renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  expect(getWorkspaceExportPolicy).not.toHaveBeenCalled();
  await openExport();
  await screen.findByRole("button", { name: "导出" });
  expect(getWorkspaceExportPolicy).toHaveBeenCalledTimes(1);
});

it("explains an unconfigured organization instead of conflating it with a policy denial", async () => {
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(null);
  renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  await openExport();
  expect(await screen.findByText(/尚未配置导出策略/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "导出" })).not.toBeInTheDocument();
});

it("does not allow a stale cached policy to authorize export during a new read", async () => {
  const { queryClient } = renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  await openExport();
  await screen.findByRole("button", { name: "导出" });
  let finish!: (next: CollectionPolicy) => void;
  vi.mocked(getWorkspaceExportPolicy).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await act(async () => {
    void queryClient.invalidateQueries({ queryKey: collectionsKeys.policy });
  });
  await waitFor(() => expect(getWorkspaceExportPolicy).toHaveBeenCalledTimes(2));
  const stale = screen.queryByRole("button", { name: "导出" });
  if (stale) expect(stale).toBeDisabled();
  else expect(screen.getByRole("status")).toHaveTextContent("正在读取导出策略");
  await act(async () => finish({ ...policy, enabled: false }));
  expect(exportComparisonSet).not.toHaveBeenCalled();
});

it("retains the idempotency key for an explicit retry of the same failed intent", async () => {
  vi.mocked(exportComparisonSet).mockRejectedValueOnce(new Error("Response unavailable"));
  renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  await openExport();
  fireEvent.click(await screen.findByRole("button", { name: "导出" }));
  await screen.findByText("Response unavailable");
  fireEvent.click(screen.getByRole("button", { name: "导出" }));
  await waitFor(() => expect(exportComparisonSet).toHaveBeenCalledTimes(2));
  expect(vi.mocked(exportComparisonSet).mock.calls[1][1].idempotency_key).toBe(
    vi.mocked(exportComparisonSet).mock.calls[0][1].idempotency_key,
  );
});

it("creates a different intent when format changes after a rejected export", async () => {
  vi.mocked(exportComparisonSet).mockRejectedValueOnce(new Error("Response unavailable"));
  renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  await openExport();
  fireEvent.click(await screen.findByRole("button", { name: "导出" }));
  await screen.findByText("Response unavailable");
  fireEvent.change(screen.getByLabelText("导出格式"), { target: { value: "xlsx" } });
  fireEvent.click(screen.getByRole("button", { name: "导出" }));
  await waitFor(() => expect(exportComparisonSet).toHaveBeenCalledTimes(2));
  expect(vi.mocked(exportComparisonSet).mock.calls[1][1].idempotency_key).not.toBe(
    vi.mocked(exportComparisonSet).mock.calls[0][1].idempotency_key,
  );
});

it("does not start a download after the selected record has unmounted", async () => {
  let finish!: (blob: Blob) => void;
  vi.mocked(exportComparisonSet).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const { unmount } = renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  await openExport();
  fireEvent.click(await screen.findByRole("button", { name: "导出" }));
  await waitFor(() => expect(exportComparisonSet).toHaveBeenCalledTimes(1));
  unmount();
  await act(async () => finish(new Blob(["{}"])));
  expect(downloadBlob).not.toHaveBeenCalled();
});

it("starts a new key when the authorized policy fingerprint changes after failure", async () => {
  vi.mocked(exportComparisonSet).mockRejectedValueOnce(new Error("Response unavailable"));
  const { queryClient } = renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  await openExport();
  fireEvent.click(await screen.findByRole("button", { name: "导出" }));
  await screen.findByText("Response unavailable");
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue({ ...policy, policy_sha256: "b".repeat(64) });
  await act(async () => {
    await queryClient.invalidateQueries({ queryKey: collectionsKeys.policy });
  });
  fireEvent.click(await screen.findByRole("button", { name: "导出" }));
  await waitFor(() => expect(exportComparisonSet).toHaveBeenCalledTimes(2));
  expect(vi.mocked(exportComparisonSet).mock.calls[1][1].idempotency_key).not.toBe(
    vi.mocked(exportComparisonSet).mock.calls[0][1].idempotency_key,
  );
});

it("keeps export unavailable while the list version is stale", async () => {
  renderWithQueryClient(<CollectionExport detail={detail} changing={false} stale />);
  await openExport();
  const submit = await screen.findByRole("button", { name: "导出" });
  expect(submit).toBeDisabled();
  expect(screen.getByText(/当前列表刷新失败/)).toBeVisible();
});

it("rejects missing required field permissions even for a malformed read fixture", async () => {
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue({ ...policy, allowed_fields: ["position", "id"] });
  renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  await openExport();
  expect(await screen.findByText(/导出策略缺少必需字段/)).toBeVisible();
  expect(screen.getByRole("button", { name: "导出" })).toBeDisabled();
});

it("clears the previous failure presentation after selecting a different format", async () => {
  vi.mocked(exportComparisonSet).mockRejectedValueOnce(new Error("Previous failure"));
  renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  await openExport();
  fireEvent.click(await screen.findByRole("button", { name: "导出" }));
  await screen.findByText("Previous failure");
  fireEvent.change(screen.getByLabelText("导出格式"), { target: { value: "xlsx" } });
  expect(screen.queryByText("Previous failure")).not.toBeInTheDocument();
});

it("clears the previous completed presentation after selecting different fields", async () => {
  renderWithQueryClient(<CollectionExport detail={detail} changing={false} />);
  await openExport();
  fireEvent.click(await screen.findByRole("button", { name: "导出" }));
  await screen.findByText("列表 v2 的导出文件已生成");
  fireEvent.click(screen.getByRole("checkbox", { name: "描述" }));
  expect(screen.queryByText("列表 v2 的导出文件已生成")).not.toBeInTheDocument();
});
