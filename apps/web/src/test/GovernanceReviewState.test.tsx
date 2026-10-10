import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import type { EntityResolutionCase, StagedFact } from "../lib/contracts/governance";
import {
  decideEntityResolution,
  decideStagedFact,
  governanceKeys,
  loadEntityResolutionHistory,
  loadEntityResolutionImpact,
  loadFactComparison,
  loadGovernanceQueues,
  loadProjectionMaintenanceAccess,
  loadPublicationBatches,
} from "../lib/contracts/governance";
import { setLocale } from "../lib/i18n";
import { GovernanceView } from "../views/GovernanceView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/governance", async (original) => ({
  ...(await original<typeof import("../lib/contracts/governance")>()),
  loadGovernanceQueues: vi.fn(),
  loadEntityResolutionHistory: vi.fn(),
  loadEntityResolutionImpact: vi.fn(),
  loadFactComparison: vi.fn(),
  loadPublicationBatches: vi.fn(),
  loadProjectionMaintenanceAccess: vi.fn(),
  decideStagedFact: vi.fn(),
  decideEntityResolution: vi.fn(),
}));
const fact: StagedFact = {
  id: "review-fact-1",
  fact_kind: "program",
  fact_key: "program:controlled",
  payload: { drug: { name: "原始药物 A" }, phase: "phase_2" },
  raw_payload: { drug: { name: "原始药物 A" }, phase: "phase_2" },
  normalization_version: null,
  source_document_id: "original-document",
  source_locator: "mechanism:controlled",
  source_quote: "Original scientific quote.",
  confidence: 0.9,
  status: "review_pending",
  quality_findings: [],
  conflict_with_ids: [],
  created_at: "2026-10-10T00:00:00Z",
};
const identity: EntityResolutionCase = {
  id: "review-case",
  source_entity_id: "original-entity",
  source_entity_name: "ALK",
  candidate_entity_id: "candidate-entity",
  candidate_entity_name: "ALK kinase",
  entity_type: "target",
  score: 0.6,
  risk_tier: "high",
  reasons: [],
  status: "pending",
  proposed_by: "governed_ai_extraction",
  reviewed_by_user_id: null,
  reviewed_at: null,
  review_notes: null,
  created_at: "2026-10-10T00:00:00Z",
  updated_at: "2026-10-10T00:00:00Z",
};
const impact = {
  case: identity,
  source_reference_count: 1,
  candidate_reference_count: 2,
  source_trusted_identifier_count: 0,
  candidate_trusted_identifier_count: 1,
  recommended_canonical_entity_id: identity.candidate_entity_id,
  recommendation_reasons: ["verified_trusted_identifier_count"],
  active_alias_entity_id: null,
  active_canonical_entity_id: null,
  rollback_available: false,
  references: [],
  decisions: [],
};
beforeEach(() => {
  vi.resetAllMocks();
  setLocale("zh-CN");
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [fact], identityCases: [identity] });
  vi.mocked(loadEntityResolutionHistory).mockResolvedValue([]);
  vi.mocked(loadEntityResolutionImpact).mockResolvedValue(impact);
  vi.mocked(loadFactComparison).mockResolvedValue({
    fact,
    origin: null,
    conflicts: [],
    conflict_total: 0,
    unavailable_conflicts: 0,
    truncated: false,
  });
  vi.mocked(loadPublicationBatches).mockResolvedValue([]);
  vi.mocked(loadProjectionMaintenanceAccess).mockResolvedValue(false);
});

it("freezes the active decision intent and preserves its draft while language changes", async () => {
  let finish!: (value: StagedFact) => void;
  vi.mocked(decideStagedFact).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  renderWithQueryClient(<GovernanceView />);
  const notes = await screen.findByRole("textbox", { name: "审核意见" });
  fireEvent.change(notes, { target: { value: "User-owned 原始审核依据" } });
  const approve = screen.getByRole("button", { name: "批准并发布" });
  await waitFor(() => expect(approve).toBeEnabled());
  fireEvent.click(approve);
  fireEvent.click(approve);
  await waitFor(() => expect(decideStagedFact).toHaveBeenCalledOnce());
  expect(notes).toBeDisabled();
  expect(screen.getByRole("tab", { name: /^实体消歧/ })).toBeDisabled();
  expect(screen.getByRole("tab", { name: /^质量运营/ })).toBeDisabled();
  await act(() => setLocale("en"));
  expect(screen.getByRole("textbox", { name: "Review notes" })).toHaveValue("User-owned 原始审核依据");
  expect(screen.getByRole("button", { name: "Approve and publish" })).toBeDisabled();
  expect(loadProjectionMaintenanceAccess).toHaveBeenCalledTimes(1);
  await act(() => finish({ ...fact, status: "published" }));
  expect(vi.mocked(decideStagedFact).mock.calls[0]?.[0]).toEqual({
    stagedFactId: fact.id,
    decision: "approve",
    notes: "User-owned 原始审核依据",
  });
});

it("retains an explicit canonical choice when impact data is refreshed", async () => {
  const { queryClient } = renderWithQueryClient(<GovernanceView />);
  fireEvent.click(await screen.findByRole("tab", { name: /^实体消歧/ }));
  const choice = await screen.findByRole("combobox", { name: /^规范实体保留/ });
  expect(choice).toHaveValue(identity.candidate_entity_id);
  fireEvent.change(choice, { target: { value: identity.source_entity_id } });
  vi.mocked(loadEntityResolutionImpact).mockResolvedValue({ ...impact, candidate_reference_count: 3 });
  await act(() => queryClient.refetchQueries({ queryKey: governanceKeys.identityImpact(identity.id), exact: true }));
  await waitFor(() => expect(screen.getByText("候选实体引用").parentElement).toHaveTextContent("3"));
  expect(choice).toHaveValue(identity.source_entity_id);
  expect(decideEntityResolution).not.toHaveBeenCalled();
});

it("hides a cached review queue after a current authorization denial", async () => {
  const { queryClient } = renderWithQueryClient(<GovernanceView />);
  await screen.findByRole("textbox", { name: "审核意见" });
  vi.mocked(loadGovernanceQueues).mockRejectedValue(new ApiError("RAW_QUEUE_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: governanceKeys.queues, exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_QUEUE_DENIAL");
  expect(screen.queryByText(fact.source_quote)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "批准并发布" })).not.toBeInTheDocument();
  expect(decideStagedFact).not.toHaveBeenCalled();
});

it("does not permit a decision when the matching evidence comparison cannot be read", async () => {
  vi.mocked(loadFactComparison).mockRejectedValue(new ApiError("RAW_COMPARISON_DENIAL", 403, null));
  renderWithQueryClient(<GovernanceView />);
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_COMPARISON_DENIAL");
  expect(screen.getByRole("button", { name: "批准并发布" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "拒绝" })).toBeDisabled();
  expect(decideStagedFact).not.toHaveBeenCalled();
});

it("preserves separate record drafts rather than discarding notes when selection changes", async () => {
  const second = {
    ...fact,
    id: "review-fact-2",
    fact_key: "program:second",
    payload: { drug: { name: "原始药物 B" } },
  };
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [fact, second], identityCases: [] });
  renderWithQueryClient(<GovernanceView />);
  fireEvent.change(await screen.findByRole("textbox", { name: "审核意见" }), { target: { value: "A draft" } });
  fireEvent.click(screen.getByRole("button", { name: /原始药物 B/ }));
  expect(screen.getByRole("textbox", { name: "审核意见" })).toHaveValue("");
  fireEvent.change(screen.getByRole("textbox", { name: "审核意见" }), { target: { value: "B draft" } });
  fireEvent.click(screen.getByRole("button", { name: /原始药物 A/ }));
  expect(screen.getByRole("textbox", { name: "审核意见" })).toHaveValue("A draft");
  expect(decideStagedFact).not.toHaveBeenCalled();
});
