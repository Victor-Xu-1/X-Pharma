import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { DomainExportControl } from "../components/DomainExportControl";
import { getWorkspaceExportPolicy } from "../lib/contracts/collections";
import { exportDomainQuery } from "../lib/contracts/domainExports";
import { downloadBlob } from "../lib/download";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/collections", () => ({
  collectionsKeys: { policy: ["collections", "export-policy"] },
  getWorkspaceExportPolicy: vi.fn(),
}));

vi.mock("../lib/contracts/domainExports", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/domainExports")>();
  return { ...actual, exportDomainQuery: vi.fn() };
});

vi.mock("../lib/download", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/download")>();
  return { ...actual, downloadBlob: vi.fn() };
});

const policy = {
  allowed_fields: ["id", "entity_type", "name", "entities.id", "entities.name"],
  allowed_formats: ["json" as const],
  attribution: "Licensed workspace export",
  configured_by_user_id: "11111111-1111-4111-8111-111111111111",
  created_at: "2026-07-24T00:00:00Z",
  enabled: true,
  id: "22222222-2222-4222-8222-222222222222",
  max_records_per_export: 20,
  policy_sha256: "a".repeat(64),
  policy_version: "domain-export-v1",
  updated_at: "2026-07-24T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(
    {},
    "",
    "/workspace/research?view=explorer&q=EGFR&entity_type=target&offset=50&sort_by=name",
  );
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(policy);
  vi.mocked(exportDomainQuery).mockResolvedValue(new Blob(["{}"], { type: "application/json" }));
});

it("exports only licensed fields with the canonical current domain query", async () => {
  renderWithQueryClient(<DomainExportControl dataset="entities" totalRows={5} />);

  fireEvent.click(await screen.findByText("导出", { selector: "summary" }));
  expect(await screen.findByRole("checkbox", { name: "稳定 ID" })).toBeDisabled();
  expect(screen.getByRole("checkbox", { name: "名称" })).toBeChecked();
  expect(screen.queryByRole("checkbox", { name: "描述" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "下载" }));

  await waitFor(() => expect(exportDomainQuery).toHaveBeenCalledOnce());
  expect(exportDomainQuery).toHaveBeenCalledWith({
    dataset: "entities",
    query: { q: "EGFR", entity_type: "target", sort_by: "name", review_status: "verified" },
    export_format: "json",
    fields: ["id", "name"],
    max_records: 5,
    idempotency_key: expect.any(String),
  });
  expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), "entities-query.json");
});

it("renders an explicit locked state when the policy disables exports", async () => {
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue({ ...policy, enabled: false });
  renderWithQueryClient(<DomainExportControl dataset="entities" totalRows={5} />);

  fireEvent.click(screen.getByText("导出", { selector: "summary" }));
  expect(await screen.findByText("本组织导出策略尚未开放该领域导出。")).toBeVisible();
  expect(screen.queryByRole("button", { name: "下载" })).not.toBeInTheDocument();
  expect(exportDomainQuery).not.toHaveBeenCalled();
});

it("keeps an in-flight export visible and immutable, then allows recovery from its error", async () => {
  let rejectExport: (error: Error) => void = () => {};
  vi.mocked(exportDomainQuery).mockReturnValue(
    new Promise<Blob>((_resolve, reject) => {
      rejectExport = reject;
    }),
  );
  renderWithQueryClient(
    <>
      <DomainExportControl dataset="entities" totalRows={5} />
      <button type="button">外部操作</button>
    </>,
  );
  const summary = await screen.findByText("导出", { selector: "summary" });
  fireEvent.click(summary);
  const details = summary.closest("details") as HTMLDetailsElement;
  const field = await screen.findByRole("checkbox", { name: "名称" });
  fireEvent.click(screen.getByRole("button", { name: "下载" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "生成中" })).toBeDisabled());
  expect(screen.getByRole("combobox", { name: "格式" })).toBeDisabled();
  expect(field).toBeDisabled();
  const pendingForm = details.querySelector("form");
  if (!pendingForm) throw new Error("Expected the pending export form");
  fireEvent.submit(pendingForm);
  expect(exportDomainQuery).toHaveBeenCalledOnce();
  fireEvent.keyDown(field, { key: "Escape" });
  fireEvent.click(summary);
  fireEvent.pointerDown(screen.getByRole("button", { name: "外部操作" }));
  expect(details.open).toBe(true);
  await act(async () => rejectExport(new Error("导出服务暂时不可用")));
  expect(await screen.findByRole("alert")).toHaveTextContent("导出服务暂时不可用");
  expect(screen.getByRole("button", { name: "下载" })).toBeEnabled();
  expect(field).toBeEnabled();
  expect(field).toBeChecked();
  field.focus();
  fireEvent.keyDown(field, { key: "Escape" });
  expect(details.open).toBe(false);
  expect(summary).toHaveFocus();
  expect(exportDomainQuery).toHaveBeenCalledOnce();
  expect(downloadBlob).not.toHaveBeenCalled();
});

it("offers an explicit policy read retry instead of misreporting a connection failure as a license denial", async () => {
  vi.mocked(getWorkspaceExportPolicy).mockRejectedValueOnce(new Error("策略服务连接中断"));
  renderWithQueryClient(<DomainExportControl dataset="entities" totalRows={5} />);
  fireEvent.click(await screen.findByText("导出", { selector: "summary" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("策略服务连接中断");
  expect(screen.queryByText("当前账号或数据许可未开放该领域导出")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "下载" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重新读取导出策略" }));
  expect(await screen.findByRole("checkbox", { name: "稳定 ID" })).toBeDisabled();
  expect(exportDomainQuery).not.toHaveBeenCalled();
});

it("explains zero query results without inventing a permission restriction", async () => {
  renderWithQueryClient(<DomainExportControl dataset="entities" totalRows={0} />);
  fireEvent.click(await screen.findByText("导出", { selector: "summary" }));
  expect(await screen.findByText("当前查询没有可导出结果；调整查询条件后再导出。")).toBeVisible();
  expect(screen.queryByRole("button", { name: "下载" })).not.toBeInTheDocument();
  expect(exportDomainQuery).not.toHaveBeenCalled();
});

it("keeps an unconfigured policy distinct from an explicit disabled policy", async () => {
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(null);
  renderWithQueryClient(<DomainExportControl dataset="entities" totalRows={5} />);
  fireEvent.click(screen.getByText("导出", { selector: "summary" }));
  expect(await screen.findByText("本组织尚未配置导出策略；请联系管理员。")).toBeVisible();
  expect(screen.queryByRole("button", { name: "下载" })).not.toBeInTheDocument();
  expect(exportDomainQuery).not.toHaveBeenCalled();
});

it("keeps a pending policy read distinct from a pending export", async () => {
  vi.mocked(getWorkspaceExportPolicy).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<DomainExportControl dataset="entities" totalRows={5} />);
  fireEvent.click(screen.getByText("导出", { selector: "summary" }));
  expect(await screen.findByRole("status")).toHaveTextContent("正在读取导出策略");
  expect(screen.queryByRole("button", { name: "下载" })).not.toBeInTheDocument();
  expect(exportDomainQuery).not.toHaveBeenCalled();
});

it("fails closed on a stale cached policy read and preserves selected fields after a successful reread", async () => {
  const { queryClient } = renderWithQueryClient(<DomainExportControl dataset="entities" totalRows={5} />);
  fireEvent.click(screen.getByText("导出", { selector: "summary" }));
  const name = await screen.findByRole("checkbox", { name: "名称" });
  fireEvent.click(name);
  expect(name).not.toBeChecked();
  vi.mocked(getWorkspaceExportPolicy).mockRejectedValueOnce(new Error("最新策略暂时无法读取"));
  await act(async () => {
    await queryClient.refetchQueries({ queryKey: ["collections", "export-policy"] });
  });
  expect(await screen.findByRole("alert")).toHaveTextContent("最新策略暂时无法读取");
  expect(screen.queryByRole("button", { name: "下载" })).not.toBeInTheDocument();
  const form = screen.getByText("导出", { selector: "summary" }).closest("details")?.querySelector("form");
  if (!form) throw new Error("Expected an export policy feedback form");
  fireEvent.submit(form);
  expect(exportDomainQuery).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "重新读取导出策略" }));
  expect(await screen.findByRole("checkbox", { name: "名称" })).not.toBeChecked();
  expect(screen.getByRole("checkbox", { name: "稳定 ID" })).toBeDisabled();
  expect(exportDomainQuery).not.toHaveBeenCalled();
});
