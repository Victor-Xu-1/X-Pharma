import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import {
  commercialKeys,
  type DataRetentionPolicy,
  executeCommercialOperation,
  type LifecycleWorkspace,
  loadCommercialOverview,
  loadLifecycleWorkspace,
} from "../lib/contracts/commercial";
import { setLocale } from "../lib/i18n";
import { CommercialView } from "../views/CommercialView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/commercial", async (original) => ({
  ...(await original<typeof import("../lib/contracts/commercial")>()),
  loadCommercialOverview: vi.fn(),
  loadLifecycleWorkspace: vi.fn(),
  executeCommercialOperation: vi.fn(),
}));
const policy: DataRetentionPolicy = {
  id: "controlled-retention",
  data_class: "commercial_export_artifact",
  policy_version: 2,
  retention_seconds: 86400,
  legal_basis: "Original policy basis <source>",
  geographic_scope: ["CN"],
  active: false,
  configured_by_user_id: "controlled-admin",
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
};
const workspace: LifecycleWorkspace = {
  retentionPolicies: [policy],
  legalHolds: [],
  lifecycleEvents: [],
  purgeCandidates: [],
  deletedSourceAssets: [],
  sourcePurgeCandidates: [
    {
      id: "controlled-source-asset",
      data_source_id: "controlled-source",
      logical_path: "literature/original <source>.md",
      file_name: "original <source>.md",
      state: "missing",
      missing_since: "2026-09-01T00:00:00Z",
      retention_eligible: true,
      version_count: 2,
      raw_object_count: 2,
      extracted_object_count: 2,
      extraction_run_count: 1,
      staged_fact_count: 0,
      published_fact_count: 0,
      evidence_claim_count: 0,
      knowledge_citation_count: 0,
      retrieval_projection_count: 1,
      shared_document_count: 0,
      other_document_reference_count: 0,
      blockers: [],
    },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  setLocale("en");
  vi.mocked(loadCommercialOverview).mockResolvedValue({
    as_of: policy.created_at,
    period_start: policy.created_at,
    subscriptions: [],
    open_risk_count: 0,
  });
  vi.mocked(loadLifecycleWorkspace).mockResolvedValue(workspace);
});
it("does not infer source retention eligibility merely from the absence of returned blockers", async () => {
  vi.mocked(loadLifecycleWorkspace).mockResolvedValue({
    ...workspace,
    sourcePurgeCandidates: workspace.sourcePurgeCandidates.map((asset) => ({ ...asset, retention_eligible: false })),
  });
  renderWithQueryClient(<CommercialView />);
  await openLifecycle();
  expect(screen.getByText("Not retention eligible at this read")).toBeInTheDocument();
  expect(screen.queryByText("Retention eligible at this read")).not.toBeInTheDocument();
});
async function openLifecycle() {
  fireEvent.click(await screen.findByRole("tab", { name: "Data lifecycle" }));
  await screen.findByRole("textbox", { name: "Matter reference" });
}
it("retains all unsent lifecycle form drafts across panel navigation and a language change", async () => {
  renderWithQueryClient(<CommercialView />);
  await openLifecycle();
  fireEvent.change(screen.getByRole("spinbutton", { name: "Retention period (hours)" }), { target: { value: "48" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Legal or contractual basis" }), {
    target: { value: "Unsubmitted basis <source>" },
  });
  fireEvent.change(screen.getByRole("textbox", { name: "Source legal or contractual basis" }), {
    target: { value: "Unsubmitted source basis <source>" },
  });
  fireEvent.change(screen.getByRole("textbox", { name: "Matter reference" }), {
    target: { value: "UNSUBMITTED_MATTER" },
  });
  fireEvent.change(screen.getByRole("textbox", { name: "Hold reason" }), {
    target: { value: "Unsubmitted hold reason <source>" },
  });
  fireEvent.click(screen.getByRole("tab", { name: "Contracts & quota" }));
  fireEvent.click(screen.getByRole("tab", { name: "Data lifecycle" }));
  await act(async () => {
    setLocale("zh-CN");
  });
  expect(screen.getByRole("spinbutton", { name: "保留时长（小时）" })).toHaveValue(48);
  expect(screen.getByRole("textbox", { name: "法律与合同依据" })).toHaveValue("Unsubmitted basis <source>");
  expect(screen.getByRole("textbox", { name: "源资料法律与合同依据" })).toHaveValue(
    "Unsubmitted source basis <source>",
  );
  expect(screen.getByRole("textbox", { name: "事项编号" })).toHaveValue("UNSUBMITTED_MATTER");
  expect(screen.getByRole("textbox", { name: "保全原因" })).toHaveValue("Unsubmitted hold reason <source>");
  expect(executeCommercialOperation).not.toHaveBeenCalled();
});
it("keeps dirty policy inputs on a newer server revision and requires an explicit use-latest decision", async () => {
  const { queryClient } = renderWithQueryClient(<CommercialView />);
  await openLifecycle();
  const input = screen.getByRole("textbox", { name: "Legal or contractual basis" });
  fireEvent.change(input, { target: { value: "Unsubmitted basis <source>" } });
  vi.mocked(loadLifecycleWorkspace).mockResolvedValue({
    ...workspace,
    retentionPolicies: [{ ...policy, policy_version: 3, legal_basis: "New server basis <source>" }],
  });
  await act(async () => queryClient.refetchQueries({ queryKey: commercialKeys.lifecycle, exact: true }));
  expect(input).toHaveValue("Unsubmitted basis <source>");
  const form = input.closest("form");
  if (!form) throw new Error("Retention form missing");
  await waitFor(() => expect(within(form).getByRole("button", { name: "Save policy" })).toBeDisabled());
  fireEvent.click(within(form).getByRole("button", { name: "Use latest policy" }));
  expect(input).toHaveValue("New server basis <source>");
  expect(executeCommercialOperation).not.toHaveBeenCalled();
});
it("distinguishes an existing inactive policy from a missing policy", async () => {
  renderWithQueryClient(<CommercialView />);
  await openLifecycle();
  const form = screen.getByRole("textbox", { name: "Legal or contractual basis" }).closest("form");
  if (!form) throw new Error("Retention form missing");
  expect(within(form).getByText("Inactive", { exact: true })).toBeInTheDocument();
  expect(within(form).queryByText("NOT_CONFIGURED")).not.toBeInTheDocument();
});
async function openWithdrawal() {
  await openLifecycle();
  fireEvent.click(screen.getByRole("button", { name: "Withdraw source asset original <source>.md" }));
  const dialog = screen.getByRole("dialog", { name: "Withdraw source asset" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Lifecycle action reason" }), {
    target: { value: "Original withdrawal basis <source>" },
  });
  return dialog;
}
it("shows the exact withdrawal target and requires its explicit acknowledgement before submission", async () => {
  renderWithQueryClient(<CommercialView />);
  const dialog = await openWithdrawal();
  expect(within(dialog).getByText("controlled-source-asset", { exact: true })).toBeInTheDocument();
  expect(within(dialog).getByText("literature/original <source>.md", { exact: true })).toBeInTheDocument();
  const submit = within(dialog).getByRole("button", { name: "Confirm action" });
  expect(submit).toBeDisabled();
  fireEvent.click(submit);
  expect(executeCommercialOperation).not.toHaveBeenCalled();
  fireEvent.click(
    within(dialog).getByRole("checkbox", { name: "I have checked the target and understand this action" }),
  );
  expect(submit).toBeEnabled();
});
it("reuses the captured lifecycle idempotency key on an explicit retry after failure", async () => {
  vi.mocked(executeCommercialOperation).mockRejectedValue(new Error("RAW_WITHDRAWAL_FAILURE"));
  renderWithQueryClient(<CommercialView />);
  const dialog = await openWithdrawal();
  fireEvent.click(
    within(dialog).getByRole("checkbox", { name: "I have checked the target and understand this action" }),
  );
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm action" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("RAW_WITHDRAWAL_FAILURE");
  const captured = vi.mocked(executeCommercialOperation).mock.calls[0]?.[0];
  await act(async () => {
    setLocale("zh-CN");
  });
  fireEvent.click(within(screen.getByRole("dialog", { name: "撤回源资料" })).getByRole("button", { name: "确认执行" }));
  await waitFor(() => expect(executeCommercialOperation).toHaveBeenCalledTimes(2));
  expect(vi.mocked(executeCommercialOperation).mock.calls[1]?.[0]).toEqual(captured);
});
it("does not promise an operation key for a legal-hold release endpoint that has none", async () => {
  vi.mocked(loadLifecycleWorkspace).mockResolvedValue({
    ...workspace,
    legalHolds: [
      {
        id: "controlled-hold",
        matter_reference: "Original matter <source>",
        scope_type: "tenant",
        scope_id: null,
        status: "active",
        reason: "Original hold basis",
        placed_at: policy.created_at,
        placed_by_user_id: "controlled-admin",
        release_reason: null,
        released_at: null,
        released_by_user_id: null,
      },
    ],
  });
  vi.mocked(executeCommercialOperation).mockRejectedValue(new Error("RAW_RELEASE_FAILURE"));
  renderWithQueryClient(<CommercialView />);
  await openLifecycle();
  fireEvent.click(screen.getByRole("button", { name: "Release legal hold Original matter <source>" }));
  const dialog = screen.getByRole("dialog", { name: "Release legal hold" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Lifecycle action reason" }), {
    target: { value: "Original release reason <source>" },
  });
  fireEvent.click(
    within(dialog).getByRole("checkbox", { name: "I have checked the target and understand this action" }),
  );
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm action" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("RAW_RELEASE_FAILURE");
  expect(
    within(dialog).getByText(
      "Retry reuses the same target and reason. This release endpoint has no operation key; review the latest hold before retrying.",
    ),
  ).toBeInTheDocument();
  expect(within(dialog).queryByText(/same target, reason and operation key/)).not.toBeInTheDocument();
  expect(vi.mocked(executeCommercialOperation).mock.calls[0]?.[0]).toEqual({
    kind: "release-legal-hold",
    holdId: "controlled-hold",
    requestBody: { reason: "Original release reason <source>" },
  });
});
it("will not submit an old withdrawal intent when the refreshed target has changed", async () => {
  const { queryClient } = renderWithQueryClient(<CommercialView />);
  const dialog = await openWithdrawal();
  fireEvent.click(
    within(dialog).getByRole("checkbox", { name: "I have checked the target and understand this action" }),
  );
  vi.mocked(loadLifecycleWorkspace).mockResolvedValue({ ...workspace, sourcePurgeCandidates: [] });
  await act(async () => queryClient.refetchQueries({ queryKey: commercialKeys.lifecycle, exact: true }));
  await within(dialog).findByText("This target has changed. Close this dialog and review its latest record.");
  expect(within(dialog).getByRole("button", { name: "Confirm action" })).toBeDisabled();
  expect(executeCommercialOperation).not.toHaveBeenCalled();
});
