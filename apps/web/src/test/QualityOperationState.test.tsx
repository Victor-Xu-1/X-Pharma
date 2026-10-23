import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import type { DataQualityIssue } from "../lib/contracts/governance";
import {
  actOnDataQualityIssue,
  evaluateDataQuality,
  governanceKeys,
  loadDataQualityCoverage,
  loadDataQualityIssueEvents,
  loadDataQualityIssues,
  loadDataQualityOwners,
  loadDataQualitySnapshots,
  loadGovernanceQueues,
  loadProjectionMaintenanceAccess,
  loadPublicationBatches,
} from "../lib/contracts/governance";
import { sessionKeys } from "../lib/contracts/session";
import { setLocale } from "../lib/i18n";
import { GovernanceView } from "../views/GovernanceView";
import { QualityTestHarness, qualityControlledAdmin } from "./QualityTestHarness";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/governance", async (original) => ({
  ...(await original<typeof import("../lib/contracts/governance")>()),
  loadDataQualitySnapshots: vi.fn(),
  loadDataQualityCoverage: vi.fn(),
  loadDataQualityIssues: vi.fn(),
  loadDataQualityOwners: vi.fn(),
  loadDataQualityIssueEvents: vi.fn(),
  loadGovernanceQueues: vi.fn(),
  loadPublicationBatches: vi.fn(),
  loadProjectionMaintenanceAccess: vi.fn(),
  actOnDataQualityIssue: vi.fn(),
  evaluateDataQuality: vi.fn(),
}));
const issue: DataQualityIssue = {
  id: "controlled-issue-a",
  metric_key: "completeness",
  scope_type: "tenant",
  scope_id: null,
  status: "open",
  severity: "high",
  title: "原始质量记录 A",
  description: "Original issue description",
  actual_value: 0.82,
  threshold_value: 0.95,
  comparison: "gte",
  owner_user_id: null,
  owner_display_name: null,
  sla_due_at: "2030-01-01T00:00:00Z",
  detected_at: "2026-10-10T00:00:00Z",
  acknowledged_at: null,
  resolved_at: null,
  resolution_notes: null,
  version: 1,
  last_snapshot_id: "controlled-snapshot",
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
};
beforeEach(() => {
  vi.resetAllMocks();
  setLocale("zh-CN");
  vi.mocked(loadDataQualitySnapshots).mockResolvedValue([]);
  vi.mocked(loadDataQualityCoverage).mockResolvedValue([]);
  vi.mocked(loadDataQualityIssues).mockResolvedValue([
    issue,
    { ...issue, id: "controlled-issue-b", title: "原始质量记录 B" },
  ]);
  vi.mocked(loadDataQualityOwners).mockResolvedValue([
    { id: "controlled-owner", display_name: "Original owner", role: "analyst" },
  ]);
  vi.mocked(loadDataQualityIssueEvents).mockResolvedValue([]);
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [], identityCases: [] });
  vi.mocked(loadPublicationBatches).mockResolvedValue([]);
  vi.mocked(loadProjectionMaintenanceAccess).mockResolvedValue(false);
});
it("binds explicit owner and note drafts to one issue instead of carrying them into another unassigned issue", async () => {
  renderWithQueryClient(<QualityTestHarness user={qualityControlledAdmin} />);
  const owner = await screen.findByRole("combobox", { name: "负责人" });
  await waitFor(() => expect(screen.getByRole("option", { name: /Original owner/ })).toBeInTheDocument());
  fireEvent.change(owner, { target: { value: "controlled-owner" } });
  fireEvent.change(screen.getByRole("textbox", { name: "处置说明" }), { target: { value: "A draft" } });
  fireEvent.click(screen.getByRole("button", { name: /原始质量记录 B/ }));
  expect(screen.getByRole("combobox", { name: "负责人" })).toHaveValue("");
  expect(screen.getByRole("textbox", { name: "处置说明" })).toHaveValue("");
  fireEvent.click(screen.getByRole("button", { name: /原始质量记录 A/ }));
  expect(screen.getByRole("combobox", { name: "负责人" })).toHaveValue("controlled-owner");
  expect(screen.getByRole("textbox", { name: "处置说明" })).toHaveValue("A draft");
  expect(actOnDataQualityIssue).not.toHaveBeenCalled();
});
it("freezes issue, owner, notes, filter and evaluation while one immutable action is pending", async () => {
  let finish: (value: DataQualityIssue) => void = () => {
    throw new Error("Pending action not installed");
  };
  vi.mocked(actOnDataQualityIssue).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  renderWithQueryClient(<QualityTestHarness user={qualityControlledAdmin} />);
  const owner = await screen.findByRole("combobox", { name: "负责人" });
  fireEvent.change(owner, { target: { value: "controlled-owner" } });
  await waitFor(() => expect(screen.getByRole("button", { name: "分配" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "分配" }));
  await waitFor(() => expect(actOnDataQualityIssue).toHaveBeenCalledOnce());
  expect(owner).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "处置说明" })).toBeDisabled();
  expect(screen.getByRole("combobox", { name: "事件状态" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "立即评估" })).toBeDisabled();
  expect(screen.getByRole("button", { name: /原始质量记录 B/ })).toBeDisabled();
  await act(async () => {
    setLocale("en");
  });
  expect(screen.getByRole("combobox", { name: "Owner" })).toHaveValue("controlled-owner");
  await act(async () => {
    finish({ ...issue, owner_user_id: "controlled-owner", version: 2 });
  });
  expect(vi.mocked(actOnDataQualityIssue).mock.calls[0]?.[0]).toMatchObject({
    issueId: issue.id,
    expected_version: 1,
    owner_user_id: "controlled-owner",
  });
});
it("hides cached issue content after a current authorization denial", async () => {
  const { queryClient } = renderWithQueryClient(<QualityTestHarness user={qualityControlledAdmin} />);
  await screen.findByRole("heading", { name: issue.title });
  vi.mocked(loadDataQualityIssues).mockRejectedValue(new ApiError("RAW_QUALITY_ISSUE_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: governanceKeys.qualityIssues("all"), exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_QUALITY_ISSUE_DENIAL");
  expect(screen.queryAllByText(issue.title)).toHaveLength(0);
  expect(screen.queryByRole("button", { name: "分配" })).not.toBeInTheDocument();
});
it("does not allow assignment from an owner catalog whose latest read failed", async () => {
  const { queryClient } = renderWithQueryClient(<QualityTestHarness user={qualityControlledAdmin} />);
  const owner = await screen.findByRole("combobox", { name: "负责人" });
  fireEvent.change(owner, { target: { value: "controlled-owner" } });
  vi.mocked(loadDataQualityOwners).mockRejectedValue(new ApiError("RAW_OWNER_CATALOG_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: governanceKeys.qualityOwners, exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_OWNER_CATALOG_DENIAL");
  expect(screen.getByRole("button", { name: "分配" })).toBeDisabled();
});
it("does not report an empty issue list while a failed read remains unresolved", async () => {
  vi.mocked(loadDataQualityIssues).mockRejectedValue(new Error("RAW_QUALITY_ISSUE_FAILURE"));
  renderWithQueryClient(<QualityTestHarness user={qualityControlledAdmin} />);
  await screen.findByText("RAW_QUALITY_ISSUE_FAILURE");
  expect(screen.queryByText("没有匹配的质量事件")).not.toBeInTheDocument();
});
it("does not allow a non-owner analyst to resolve or waive a ready issue", async () => {
  vi.mocked(loadDataQualityIssues).mockResolvedValue([
    { ...issue, status: "ready_to_resolve", owner_user_id: "another-owner" },
  ]);
  renderWithQueryClient(<QualityTestHarness user={{ ...qualityControlledAdmin, role: "analyst" }} />);
  await screen.findByRole("heading", { name: issue.title });
  expect(screen.queryByRole("button", { name: "复核并关闭" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "记录豁免" })).not.toBeInTheDocument();
});
it("hides denied cached event history and freezes actions until the current history is available", async () => {
  vi.mocked(loadDataQualityIssueEvents).mockResolvedValue([
    {
      id: "controlled-event",
      action: "ORIGINAL_ACTION",
      actor_type: "constructor",
      actor_id: "original-actor",
      previous_status: null,
      resulting_status: "open",
      occurred_at: issue.created_at,
      details: { original: "<source>" },
    },
  ]);
  const { queryClient } = renderWithQueryClient(<QualityTestHarness user={qualityControlledAdmin} />);
  await screen.findByText("ORIGINAL_ACTION");
  expect(screen.getByText(/constructor/, { selector: ".quality-event-history article > p" })).toBeInTheDocument();
  vi.mocked(loadDataQualityIssueEvents).mockRejectedValue(new ApiError("RAW_HISTORY_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: governanceKeys.qualityIssueEvents(issue.id), exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_HISTORY_DENIAL");
  expect(screen.queryByText("ORIGINAL_ACTION")).not.toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "处置说明" })).toBeDisabled();
});
it("preserves a failed action draft and does not present an unrelated response as a successful transition", async () => {
  vi.mocked(actOnDataQualityIssue).mockResolvedValue({ ...issue, id: "different-issue", version: 2 });
  renderWithQueryClient(<QualityTestHarness user={qualityControlledAdmin} />);
  const owner = await screen.findByRole("combobox", { name: "负责人" });
  await waitFor(() => expect(owner).toBeEnabled());
  fireEvent.change(owner, { target: { value: "controlled-owner" } });
  fireEvent.change(screen.getByRole("textbox", { name: "处置说明" }), { target: { value: "Original draft <source>" } });
  fireEvent.click(screen.getByRole("button", { name: "分配" }));
  await screen.findByText("提交结果与原事件不一致；请刷新权威记录后再操作。");
  expect(screen.getByRole("textbox", { name: "处置说明" })).toHaveValue("Original draft <source>");
  expect(screen.queryByText("处置已提交；以下状态以最新读取的记录为准。")).not.toBeInTheDocument();
});
it("retains quality drafts when another governance section is viewed and then returned to", async () => {
  renderWithQueryClient(<GovernanceView />, undefined, (client) => {
    client.setQueryData(sessionKeys.current, { mode: "local", user: qualityControlledAdmin });
  });
  fireEvent.click(await screen.findByRole("tab", { name: "质量运营" }));
  const owner = await screen.findByRole("combobox", { name: "负责人" });
  await waitFor(() => expect(owner).toBeEnabled());
  fireEvent.change(owner, { target: { value: "controlled-owner" } });
  fireEvent.change(screen.getByRole("textbox", { name: "处置说明" }), { target: { value: "Original section draft" } });
  fireEvent.click(screen.getByRole("tab", { name: /^事实审核/ }));
  fireEvent.click(screen.getByRole("tab", { name: "质量运营" }));
  expect(await screen.findByRole("textbox", { name: "处置说明" })).toHaveValue("Original section draft");
  expect(screen.getByRole("combobox", { name: "负责人" })).toHaveValue("controlled-owner");
});
