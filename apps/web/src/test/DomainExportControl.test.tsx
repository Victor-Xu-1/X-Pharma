import { fireEvent, screen, waitFor } from "@testing-library/react";
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
  expect(screen.getByRole("checkbox", { name: "稳定 ID" })).toBeDisabled();
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

  const locked = await screen.findByRole("button", { name: "导出" });
  expect(locked).toBeDisabled();
  await waitFor(() => expect(locked).toHaveAttribute("title", "当前账号或数据许可未开放该领域导出"));
});
