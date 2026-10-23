import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import type { PublicationBatch, StagedFact } from "../lib/contracts/governance";
import {
  commitPublicationBatch,
  governanceKeys,
  loadEntityResolutionHistory,
  loadFactComparison,
  loadGovernanceQueues,
  loadProjectionMaintenanceAccess,
  loadProjectionMaintenanceJobs,
  loadPublicationBatch,
  loadPublicationBatches,
  previewPublicationBatch,
  requestProjectionMaintenance,
} from "../lib/contracts/governance";
import { setLocale } from "../lib/i18n";
import { GovernanceView } from "../views/GovernanceView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/governance", async (original) => ({
  ...(await original<typeof import("../lib/contracts/governance")>()),
  loadGovernanceQueues: vi.fn(),
  loadEntityResolutionHistory: vi.fn(),
  loadFactComparison: vi.fn(),
  loadPublicationBatches: vi.fn(),
  loadPublicationBatch: vi.fn(),
  previewPublicationBatch: vi.fn(),
  commitPublicationBatch: vi.fn(),
  loadProjectionMaintenanceAccess: vi.fn(),
  loadProjectionMaintenanceJobs: vi.fn(),
  requestProjectionMaintenance: vi.fn(),
}));
const fact: StagedFact = {
  id: "controlled-fact",
  fact_kind: "program",
  payload: { drug: { name: "原始药物 A" } },
  raw_payload: { drug: { name: "原始药物 A" } },
  normalization_version: null,
  source_document_id: "original-document",
  source_locator: "page 3",
  source_quote: "Original quote.",
  confidence: 0.9,
  status: "review_pending",
  quality_findings: [],
  conflict_with_ids: [],
  created_at: "2026-10-10T00:00:00Z",
};
const preview: PublicationBatch = {
  id: "requested-batch",
  idempotency_key: "controlled-key",
  operation: "publish",
  status: "previewed",
  preview_sha256: "a".repeat(64),
  expected_count: 1,
  blocked_count: 0,
  reason: "Original basis",
  requested_by_user_id: "controlled-user",
  committed_by_user_id: null,
  committed_at: null,
  result: { requested_fact_ids: [fact.id] },
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
  items: [
    {
      id: "controlled-item",
      staged_fact_id: fact.id,
      position: 0,
      expected_status: fact.status,
      outcome: "ready",
      blockers: [],
      snapshot: { fact_kind: fact.fact_kind },
      created_at: "2026-10-10T00:00:00Z",
    },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  setLocale("en");
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [fact], identityCases: [] });
  vi.mocked(loadEntityResolutionHistory).mockResolvedValue([]);
  vi.mocked(loadFactComparison).mockResolvedValue({
    fact,
    origin: null,
    conflicts: [],
    conflict_total: 0,
    unavailable_conflicts: 0,
    truncated: false,
  });
  vi.mocked(loadPublicationBatches).mockResolvedValue([preview]);
  vi.mocked(loadPublicationBatch).mockResolvedValue(preview);
  vi.mocked(loadProjectionMaintenanceAccess).mockResolvedValue(false);
  vi.mocked(loadProjectionMaintenanceJobs).mockResolvedValue([]);
});
async function openBatches() {
  fireEvent.click(await screen.findByText("Batch publication and withdrawal"));
}
async function selectBatch() {
  await openBatches();
  fireEvent.click(await screen.findByRole("button", { name: /^Publish/ }));
  await screen.findByText(preview.preview_sha256);
}
it("freezes both batch inputs and neighboring review operations for a single pending preview", async () => {
  let finish: (value: PublicationBatch) => void = () => {
    throw new Error("Pending preview is not installed");
  };
  vi.mocked(previewPublicationBatch).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  renderWithQueryClient(<GovernanceView />);
  await openBatches();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.change(screen.getByRole("textbox", { name: "Batch review evidence" }), {
    target: { value: "Original basis" },
  });
  const submit = screen.getByRole("button", { name: "Preview publication (1)" });
  fireEvent.click(submit);
  fireEvent.click(submit);
  await waitFor(() => expect(previewPublicationBatch).toHaveBeenCalledTimes(1));
  expect(screen.getByRole("textbox", { name: "Batch review evidence" })).toBeDisabled();
  expect(screen.getByRole("checkbox")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Approve and publish" })).toBeDisabled();
  expect(screen.getByRole("tab", { name: /^Entity resolution/ })).toBeDisabled();
  await act(() => setLocale("zh-CN"));
  expect(screen.getByRole("textbox", { name: "批次审核依据" })).toHaveValue("Original basis");
  await act(() => finish(preview));
});
it("hides the cached preview hash and commit operation after a current detail permission denial", async () => {
  const { queryClient } = renderWithQueryClient(<GovernanceView />);
  await selectBatch();
  vi.mocked(loadPublicationBatch).mockRejectedValue(new ApiError("RAW_BATCH_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: governanceKeys.publicationBatch(preview.id), exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_BATCH_DENIAL");
  expect(screen.queryByText(preview.preview_sha256)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Commit publication atomically" })).not.toBeInTheDocument();
  expect(commitPublicationBatch).not.toHaveBeenCalled();
});
it("rejects a batch detail bound to another requested identifier", async () => {
  vi.mocked(loadPublicationBatch).mockResolvedValue({ ...preview, id: "another-batch" });
  renderWithQueryClient(<GovernanceView />);
  await openBatches();
  fireEvent.click(await screen.findByRole("button", { name: /^Publish/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Batch detail does not match the requested identifier");
  expect(screen.queryByRole("button", { name: "Commit publication atomically" })).not.toBeInTheDocument();
});
it("disables commit on a failed refresh instead of presenting a stale preview as currently verified", async () => {
  const { queryClient } = renderWithQueryClient(<GovernanceView />);
  await selectBatch();
  vi.mocked(loadPublicationBatch).mockRejectedValue(new ApiError("RAW_BATCH_TEMPORARY_FAILURE", 503, null));
  await act(() => queryClient.refetchQueries({ queryKey: governanceKeys.publicationBatch(preview.id), exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_BATCH_TEMPORARY_FAILURE");
  expect(screen.getByRole("button", { name: "Commit publication atomically" })).toBeDisabled();
});
it("retains the same idempotency key when explicitly retrying an unchanged preview intent", async () => {
  vi.mocked(previewPublicationBatch)
    .mockRejectedValueOnce(new Error("RAW_UNCERTAIN_PREVIEW"))
    .mockResolvedValue(preview);
  renderWithQueryClient(<GovernanceView />);
  await openBatches();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.change(screen.getByRole("textbox", { name: "Batch review evidence" }), {
    target: { value: "Original basis" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Preview publication (1)" }));
  await screen.findByText("RAW_UNCERTAIN_PREVIEW");
  fireEvent.click(screen.getByRole("button", { name: "Preview publication (1)" }));
  await waitFor(() => expect(previewPublicationBatch).toHaveBeenCalledTimes(2));
  expect(vi.mocked(previewPublicationBatch).mock.calls[1]?.[0].idempotencyKey).toBe(
    vi.mocked(previewPublicationBatch).mock.calls[0]?.[0].idempotencyKey,
  );
});
it("hides cached global maintenance controls when the access check is denied", async () => {
  vi.mocked(loadProjectionMaintenanceAccess).mockResolvedValue(true);
  const { queryClient } = renderWithQueryClient(<GovernanceView />);
  await openBatches();
  await screen.findByText("Search projection maintenance");
  vi.mocked(loadProjectionMaintenanceAccess).mockRejectedValue(new ApiError("RAW_GLOBAL_ACCESS_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: governanceKeys.projectionMaintenanceAccess, exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_GLOBAL_ACCESS_DENIAL");
  expect(screen.queryByRole("button", { name: "Atomic global projection rebuild" })).not.toBeInTheDocument();
  expect(requestProjectionMaintenance).not.toHaveBeenCalled();
});

it("requires a new explicit confirmation for every global rebuild without issuing a request on open or cancel", async () => {
  vi.mocked(loadProjectionMaintenanceAccess).mockResolvedValue(true);
  renderWithQueryClient(<GovernanceView />);
  await openBatches();
  const rebuild = await screen.findByRole("button", { name: "Atomic global projection rebuild" });
  await waitFor(() => expect(rebuild).toBeEnabled());
  fireEvent.click(rebuild);
  expect(await screen.findByRole("dialog", { name: "Rebuild global search projections" })).toBeInTheDocument();
  const confirm = screen.getByRole("button", { name: "Confirm rebuild" });
  expect(confirm).toBeDisabled();
  const acknowledgement = screen.getByRole("checkbox", {
    name: "I confirm that the global search projections for every organization need to be rebuilt",
  });
  fireEvent.click(acknowledgement);
  expect(confirm).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(requestProjectionMaintenance).not.toHaveBeenCalled();
  fireEvent.click(rebuild);
  expect(screen.getByRole("button", { name: "Confirm rebuild" })).toBeDisabled();
  expect(
    screen.getByRole("checkbox", {
      name: "I confirm that the global search projections for every organization need to be rebuilt",
    }),
  ).not.toBeChecked();
});

it("revalidates global access when refreshing jobs rather than relying on the earlier allow result", async () => {
  vi.mocked(loadProjectionMaintenanceAccess).mockResolvedValue(true);
  renderWithQueryClient(<GovernanceView />);
  await openBatches();
  const refresh = await screen.findByRole("button", { name: "Refresh maintenance jobs" });
  vi.mocked(loadProjectionMaintenanceAccess).mockRejectedValue(new ApiError("RAW_REFRESH_ACCESS_DENIAL", 403, null));
  fireEvent.click(refresh);
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_REFRESH_ACCESS_DENIAL");
  expect(screen.queryByRole("button", { name: "Atomic global projection rebuild" })).not.toBeInTheDocument();
  expect(requestProjectionMaintenance).not.toHaveBeenCalled();
});
