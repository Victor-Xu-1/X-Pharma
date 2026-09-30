import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import {
  actOnDataQualityIssue,
  commitPublicationBatch,
  decideEntityResolution,
  decideStagedFact,
  evaluateDataQuality,
  loadDataQualityCoverage,
  loadDataQualityIssueEvents,
  loadDataQualityIssues,
  loadDataQualityOwners,
  loadDataQualitySnapshots,
  loadEntityResolutionHistory,
  loadEntityResolutionImpact,
  loadGovernanceQueues,
  loadGovernanceRuns,
  loadProjectionMaintenanceAccess,
  loadProjectionMaintenanceJobs,
  loadPublicationBatch,
  loadPublicationBatches,
  previewPublicationBatch,
  requestProjectionMaintenance,
} from "../lib/contracts/governance";
import { GovernanceView } from "../views/GovernanceView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/governance", () => ({
  governanceKeys: {
    queues: ["governance", "queues"],
    identityHistory: ["governance", "identity-history"],
    identityImpact: (caseId: string) => ["governance", "identity-impact", caseId],
    qualityIssues: (status: string) => ["governance", "quality-issues", status],
    qualityIssueEvents: (issueId: string) => ["governance", "quality-issue-events", issueId],
    qualityOwners: ["governance", "quality-owners"],
    qualitySnapshots: ["governance", "quality-snapshots"],
    qualityCoverage: ["governance", "quality-coverage"],
    publicationBatches: ["governance", "publication-batches"],
    publicationBatch: (batchId: string) => ["governance", "publication-batch", batchId],
    projectionMaintenanceAccess: ["governance", "projection-maintenance-access"],
    projectionMaintenanceJobs: ["governance", "projection-maintenance-jobs"],
    runs: (status: string, limit: number, offset: number) => ["governance", "runs", status, limit, offset],
  },
  loadGovernanceQueues: vi.fn(),
  loadGovernanceRuns: vi.fn(),
  loadEntityResolutionHistory: vi.fn(),
  loadEntityResolutionImpact: vi.fn(),
  loadDataQualitySnapshots: vi.fn(),
  loadDataQualityCoverage: vi.fn(),
  loadDataQualityIssues: vi.fn(),
  loadDataQualityOwners: vi.fn(),
  loadDataQualityIssueEvents: vi.fn(),
  evaluateDataQuality: vi.fn(),
  actOnDataQualityIssue: vi.fn(),
  loadPublicationBatches: vi.fn(),
  loadPublicationBatch: vi.fn(),
  previewPublicationBatch: vi.fn(),
  commitPublicationBatch: vi.fn(),
  loadProjectionMaintenanceAccess: vi.fn(),
  loadProjectionMaintenanceJobs: vi.fn(),
  requestProjectionMaintenance: vi.fn(),
  decideStagedFact: vi.fn(),
  decideEntityResolution: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(loadGovernanceQueues).mockReset();
  vi.mocked(loadGovernanceRuns).mockReset();
  vi.mocked(loadEntityResolutionHistory).mockReset();
  vi.mocked(loadEntityResolutionImpact).mockReset();
  vi.mocked(loadDataQualitySnapshots).mockReset();
  vi.mocked(loadDataQualityCoverage).mockReset();
  vi.mocked(loadDataQualityIssues).mockReset();
  vi.mocked(loadDataQualityOwners).mockReset();
  vi.mocked(loadDataQualityIssueEvents).mockReset();
  vi.mocked(evaluateDataQuality).mockReset();
  vi.mocked(actOnDataQualityIssue).mockReset();
  vi.mocked(loadPublicationBatches).mockReset();
  vi.mocked(loadPublicationBatch).mockReset();
  vi.mocked(previewPublicationBatch).mockReset();
  vi.mocked(commitPublicationBatch).mockReset();
  vi.mocked(loadProjectionMaintenanceAccess).mockReset();
  vi.mocked(loadProjectionMaintenanceJobs).mockReset();
  vi.mocked(requestProjectionMaintenance).mockReset();
  vi.mocked(loadEntityResolutionHistory).mockResolvedValue([]);
  vi.mocked(loadDataQualitySnapshots).mockResolvedValue([]);
  vi.mocked(loadDataQualityCoverage).mockResolvedValue([]);
  vi.mocked(loadDataQualityIssues).mockResolvedValue([]);
  vi.mocked(loadDataQualityOwners).mockResolvedValue([]);
  vi.mocked(loadDataQualityIssueEvents).mockResolvedValue([]);
  vi.mocked(loadPublicationBatches).mockResolvedValue([]);
  vi.mocked(loadProjectionMaintenanceAccess).mockResolvedValue(true);
  vi.mocked(loadProjectionMaintenanceJobs).mockResolvedValue([]);
  vi.mocked(decideStagedFact).mockReset();
  vi.mocked(decideEntityResolution).mockReset();
});

it("shows auditable AI governance runs without exposing structured model output", async () => {
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [], identityCases: [] });
  vi.mocked(loadGovernanceRuns).mockResolvedValue({
    total: 1,
    limit: 30,
    offset: 0,
    current_policy_sha256: "f".repeat(64),
    items: [
      {
        id: "run-1",
        source_version_id: "version-1",
        source_asset_id: "asset-1",
        source_logical_path: "reports/egfr.pdf",
        source_file_name: "egfr.pdf",
        source_content_sha256: "a".repeat(64),
        schema_name: "pharma_document_facts",
        schema_version: "2.12",
        model_provider: "openai_compatible",
        model_name: "approved-model",
        prompt_sha256: "b".repeat(64),
        policy_sha256: "c".repeat(64),
        input_sha256: "d".repeat(64),
        policy_current: false,
        status: "failed",
        validation_errors: [{ code: "quote_not_found" }],
        input_tokens: 120,
        output_tokens: 30,
        estimated_cost: "0.012345",
        started_at: "2026-07-25T01:00:00Z",
        completed_at: "2026-07-25T01:00:05Z",
        created_at: "2026-07-25T01:00:00Z",
      },
    ],
  });

  renderWithQueryClient(<GovernanceView />);
  fireEvent.click(await screen.findByRole("tab", { name: "运行追踪" }));

  expect(await screen.findByRole("heading", { name: "egfr.pdf" })).toBeInTheDocument();
  expect(screen.getByText("openai_compatible / approved-model")).toBeInTheDocument();
  expect(screen.getByText("历史策略")).toBeInTheDocument();
  expect(screen.getByText(/quote_not_found/)).toBeInTheDocument();
  expect(screen.getByText("a".repeat(64))).toBeInTheDocument();
  expect(loadGovernanceRuns).toHaveBeenCalledWith("all", 30, 0, expect.any(AbortSignal));
  expect(screen.queryByText(/structured model output/i)).not.toBeInTheDocument();
});

it("shows model and normalized payloads and requires notes for conflict approval", async () => {
  const facts = [
    {
      id: "fact-1",
      fact_kind: "structure",
      raw_payload: { canonical_smiles: "[Na+].[O-]C(C)=O", standard_inchi_key: null },
      payload: { canonical_smiles: "CC(=O)O", standard_inchi_key: "QTBSBXVTEAMEQO-UHFFFAOYSA-N" },
      normalization_version: "rdkit-2026.03.3/cleanup-fragment-uncharger-tautomer-v1",
      source_document_id: "document-1",
      source_locator: "page 3",
      source_quote: "Compound A has a reported structure.",
      confidence: 0.99,
      status: "conflict" as const,
      quality_findings: [{ code: "structure_authority_mismatch" }],
      conflict_with_ids: [],
      created_at: "2026-07-16T00:00:00Z",
    },
  ];
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts, identityCases: [] });

  renderWithQueryClient(<GovernanceView />);

  expect(await screen.findByText("模型原始输出")).toBeInTheDocument();
  expect(screen.getByText("平台规范化结果")).toBeInTheDocument();
  expect(screen.getByText(/rdkit-2026\.03\.3/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /批准并发布/ }));
  expect(screen.getByRole("alert")).toHaveTextContent("冲突事实批准前必须填写审核意见");
  expect(decideStagedFact).not.toHaveBeenCalled();
});

it("previews and atomically commits selected facts as an auditable publication batch", async () => {
  const fact = {
    id: "fact-batch-1",
    fact_kind: "claim",
    raw_payload: { value: "EGFR" },
    payload: { value: "EGFR" },
    normalization_version: null,
    source_document_id: "document-1",
    source_locator: "page=2",
    source_quote: "EGFR is a validated target.",
    confidence: 0.97,
    status: "review_pending" as const,
    quality_findings: [],
    conflict_with_ids: [],
    created_at: "2026-07-25T01:00:00Z",
  };
  const preview = {
    id: "batch-preview-1",
    idempotency_key: "governance-ui:publish:test-preview",
    operation: "publish" as const,
    status: "previewed" as const,
    preview_sha256: "a".repeat(64),
    expected_count: 1,
    blocked_count: 0,
    reason: "Source and quote verified",
    requested_by_user_id: "reviewer-1",
    committed_by_user_id: null,
    committed_at: null,
    result: { requested_fact_ids: [fact.id] },
    created_at: "2026-07-25T01:01:00Z",
    updated_at: "2026-07-25T01:01:00Z",
    items: [
      {
        id: "batch-item-1",
        staged_fact_id: fact.id,
        position: 0,
        expected_status: "review_pending",
        outcome: "ready",
        blockers: [],
        snapshot: { fact_kind: "claim" },
        created_at: "2026-07-25T01:01:00Z",
      },
    ],
  };
  const committed = {
    ...preview,
    status: "committed" as const,
    committed_by_user_id: "reviewer-1",
    committed_at: "2026-07-25T01:02:00Z",
  };
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [fact], identityCases: [] });
  vi.mocked(previewPublicationBatch).mockResolvedValue(preview);
  vi.mocked(loadPublicationBatch).mockResolvedValue(preview);
  vi.mocked(commitPublicationBatch).mockResolvedValue(committed);

  renderWithQueryClient(<GovernanceView />);
  fireEvent.click(await screen.findByText("批次发布与撤回"));
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.change(screen.getByRole("textbox", { name: "批次审核依据" }), {
    target: { value: "Source and quote verified" },
  });
  fireEvent.click(screen.getByRole("button", { name: /生成发布预览 \(1\)/ }));

  await waitFor(() => expect(previewPublicationBatch).toHaveBeenCalledOnce());
  expect(vi.mocked(previewPublicationBatch).mock.calls[0]?.[0]).toMatchObject({
    operation: "publish",
    stagedFactIds: [fact.id],
    reason: "Source and quote verified",
  });
  expect(await screen.findByText("a".repeat(64))).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "原子提交发布" }));

  await waitFor(() => expect(commitPublicationBatch).toHaveBeenCalledOnce());
  expect(vi.mocked(commitPublicationBatch).mock.calls[0]?.[0]).toEqual({
    batchId: preview.id,
    previewSha256: preview.preview_sha256,
  });
});

it("does not expose global projection controls to tenant-only administrators", async () => {
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [], identityCases: [] });
  vi.mocked(loadProjectionMaintenanceAccess).mockResolvedValue(false);

  renderWithQueryClient(<GovernanceView />);
  fireEvent.click(await screen.findByText("批次发布与撤回"));

  await waitFor(() => expect(loadProjectionMaintenanceAccess).toHaveBeenCalledOnce());
  expect(screen.queryByText("检索投影维护")).not.toBeInTheDocument();
  expect(loadProjectionMaintenanceJobs).not.toHaveBeenCalled();
});

it("does not announce batch-detail loading before a batch is selected", async () => {
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [], identityCases: [] });

  renderWithQueryClient(<GovernanceView />);
  fireEvent.click(await screen.findByText("批次发布与撤回"));

  expect(await screen.findByText("批次历史")).toBeInTheDocument();
  expect(screen.queryByText("正在读取批次明细")).not.toBeInTheDocument();
  expect(loadPublicationBatch).not.toHaveBeenCalled();
});

it("operates quality trends, ownership and SLA events without leaving the governance workspace", async () => {
  const metric = (label: string, value: number, status: string) => ({
    label,
    value,
    numerator: Math.round(value * 100),
    denominator: 100,
    applicable: true,
    threshold: 0.95,
    comparison: "gte",
    status,
    severity: "high",
  });
  const snapshot = {
    id: "quality-snapshot-1",
    trigger: "scheduled" as const,
    definitions_version: "quality-v1",
    window_start: "2026-07-24T00:00:00Z",
    window_end: "2026-07-25T00:00:00Z",
    measured_at: "2026-07-25T00:00:00Z",
    metrics: {
      completeness: metric("解析完整率", 0.82, "failed"),
      duplicate_rate: { ...metric("重复率", 0.02, "passed"), comparison: "lte", threshold: 0.05 },
      citation_coverage: metric("引用覆盖率", 0.98, "failed"),
      freshness_coverage: metric("来源新鲜度覆盖", 0.9, "failed"),
      ingestion_success: metric("入库成功率", 0.96, "passed"),
      drift: { ...metric("指标漂移", 0.04, "passed"), comparison: "lte", threshold: 0.1 },
    },
    created_at: "2026-07-25T00:00:00Z",
  };
  const issue = {
    id: "quality-issue-1",
    metric_key: "completeness",
    scope_type: "tenant",
    scope_id: null,
    status: "open" as const,
    severity: "high" as const,
    title: "解析完整率未达到质量阈值",
    description: "当前值 82.00%，要求至少 95.00%；样本 82/100。",
    actual_value: 0.82,
    threshold_value: 0.95,
    comparison: "gte" as const,
    owner_user_id: null,
    owner_display_name: null,
    sla_due_at: "2026-07-26T00:00:00Z",
    detected_at: "2026-07-25T00:00:00Z",
    acknowledged_at: null,
    resolved_at: null,
    resolution_notes: null,
    version: 1,
    last_snapshot_id: snapshot.id,
    created_at: "2026-07-25T00:00:00Z",
    updated_at: "2026-07-25T00:00:00Z",
  };
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [], identityCases: [] });
  vi.mocked(loadDataQualitySnapshots).mockResolvedValue([snapshot]);
  vi.mocked(loadDataQualityCoverage).mockResolvedValue([
    {
      source_id: "quality-source-1",
      name: "ClinicalTrials.gov",
      source_type: "clinicaltrials_gov",
      dataset_key: "clinical_trials",
      owner: "Data Quality",
      state: "active",
      data_classification: "public",
      authorization_scopes: ["public:api"],
      authorization_valid_until: null,
      authorization_status: "valid",
      asset_count: 100,
      active_asset_count: 100,
      parsed_asset_count: 96,
      parse_missing_count: 4,
      parse_coverage: 0.96,
      fact_count: 100,
      published_fact_count: 96,
      review_pending_fact_count: 4,
      conflict_fact_count: 0,
      rejected_fact_count: 0,
      published_fact_coverage: 0.96,
      conflict_rate: 0,
      window_start: "2026-07-24T00:00:00Z",
      measured_at: "2026-07-25T00:00:00Z",
      run_count: 4,
      successful_run_count: 4,
      failed_run_count: 0,
      ingestion_success_rate: 1,
      last_scanned_at: "2026-07-25T00:00:00Z",
      last_success_at: "2026-07-25T00:00:00Z",
      expected_freshness_seconds: 86400,
      freshness_age_seconds: 3600,
      freshness_status: "fresh",
      consecutive_failures: 0,
      failure_sla_age_seconds: null,
      failure_sla_status: "healthy",
      last_error_present: false,
    },
  ]);
  vi.mocked(loadDataQualityIssues).mockResolvedValue([issue]);
  vi.mocked(loadDataQualityOwners).mockResolvedValue([
    { id: "quality-owner-1", display_name: "Quality Owner", role: "analyst" },
  ]);
  vi.mocked(loadDataQualityIssueEvents).mockResolvedValue([
    {
      id: "quality-event-1",
      action: "opened",
      actor_type: "system",
      actor_id: "quality-worker",
      previous_status: null,
      resulting_status: "open",
      details: { snapshot_id: snapshot.id },
      occurred_at: "2026-07-25T00:00:00Z",
    },
  ]);
  vi.mocked(evaluateDataQuality).mockResolvedValue(snapshot);
  vi.mocked(actOnDataQualityIssue).mockResolvedValue({
    ...issue,
    owner_user_id: "quality-owner-1",
    owner_display_name: "Quality Owner",
    version: 2,
  });

  renderWithQueryClient(<GovernanceView />);
  fireEvent.click(await screen.findByRole("tab", { name: "质量运营" }));

  expect(await screen.findByRole("heading", { name: "数据质量运营" })).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "来源覆盖与授权" })).toBeInTheDocument();
  expect(await screen.findByRole("status")).toHaveTextContent("当前快照之外仍有 1 个事件尚未结案，其中 1 个已超过 SLA");
  expect(screen.getByText("ClinicalTrials.gov")).toBeInTheDocument();
  expect(vi.mocked(loadDataQualityCoverage)).toHaveBeenCalledOnce();
  expect((await screen.findAllByText("82.0%")).length).toBeGreaterThan(0);
  expect((await screen.findAllByText("解析完整率未达到质量阈值")).length).toBe(2);
  fireEvent.change(screen.getByLabelText("负责人"), { target: { value: "quality-owner-1" } });
  fireEvent.click(screen.getByRole("button", { name: "分配" }));
  await waitFor(() => expect(actOnDataQualityIssue).toHaveBeenCalledOnce());
  expect(vi.mocked(actOnDataQualityIssue).mock.calls[0]?.[0]).toEqual({
    issueId: issue.id,
    action: "assign",
    expected_version: 1,
    owner_user_id: "quality-owner-1",
    notes: null,
  });
  fireEvent.click(screen.getByRole("button", { name: "立即评估" }));
  await waitFor(() => expect(evaluateDataQuality).toHaveBeenCalledOnce());
});

it("reviews an entity resolution without destructively merging records", async () => {
  const resolution = {
    id: "case-1",
    source_entity_id: "entity-source",
    source_entity_name: "ALK",
    candidate_entity_id: "entity-candidate",
    candidate_entity_name: "ALK kinase",
    entity_type: "target" as const,
    score: 0.6,
    risk_tier: "high" as const,
    reasons: [{ code: "trusted_identifier_conflict", weight: -0.4 }],
    status: "pending" as const,
    proposed_by: "governed_ai_extraction",
    reviewed_by_user_id: null,
    reviewed_at: null,
    review_notes: null,
    created_at: "2026-07-18T00:00:00Z",
    updated_at: "2026-07-18T00:00:00Z",
  };
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [], identityCases: [resolution] });
  vi.mocked(loadEntityResolutionImpact).mockResolvedValue({
    case: resolution,
    source_reference_count: 1,
    candidate_reference_count: 2,
    source_trusted_identifier_count: 0,
    candidate_trusted_identifier_count: 1,
    recommended_canonical_entity_id: "entity-candidate",
    recommendation_reasons: ["verified_trusted_identifier_count", "governed_reference_count"],
    active_alias_entity_id: null,
    active_canonical_entity_id: null,
    rollback_available: false,
    references: [
      {
        domain: "target_intelligence",
        table: "target_profiles",
        column: "entity_id",
        source_count: 0,
        candidate_count: 1,
      },
    ],
    decisions: [],
  });
  vi.mocked(decideEntityResolution).mockResolvedValue(resolution);

  renderWithQueryClient(<GovernanceView />);

  fireEvent.click(await screen.findByRole("tab", { name: /实体消歧 1/ }));
  expect(screen.getByText("候选规范实体：ALK kinase")).toBeInTheDocument();
  expect(screen.getByText(/trusted_identifier_conflict/)).toBeInTheDocument();
  await screen.findByRole("heading", { name: "跨域影响分析" });

  fireEvent.click(screen.getByRole("button", { name: /设为同一实体/ }));
  expect(screen.getByRole("alert")).toHaveTextContent("设为同一实体时必须填写审核依据");
  fireEvent.click(screen.getByRole("button", { name: /保持独立/ }));
  expect(screen.getByRole("alert")).toHaveTextContent("保持实体独立时必须填写原因");
  fireEvent.change(screen.getByRole("textbox", { name: "审核意见" }), { target: { value: "HGNC ID 不一致" } });
  fireEvent.click(screen.getByRole("button", { name: /保持独立/ }));

  await waitFor(() => expect(decideEntityResolution).toHaveBeenCalledOnce());
  expect(vi.mocked(decideEntityResolution).mock.calls[0]?.[0]).toEqual({
    caseId: "case-1",
    action: "reject",
    expectedStatus: "pending",
    canonicalEntityId: null,
    notes: "HGNC ID 不一致",
  });
});

it("shows immutable merge impact and requires an explicit basis before rollback", async () => {
  const approved = {
    id: "case-approved",
    source_entity_id: "entity-source",
    source_entity_name: "HER2",
    candidate_entity_id: "entity-candidate",
    candidate_entity_name: "ERBB2",
    entity_type: "target" as const,
    score: 0.98,
    risk_tier: "medium" as const,
    reasons: [{ code: "trusted_identifier_match", weight: 0.8 }],
    status: "approved" as const,
    proposed_by: "governed_ai_extraction",
    reviewed_by_user_id: "reviewer-1",
    reviewed_at: "2026-07-25T02:00:00Z",
    review_notes: "HGNC verified",
    created_at: "2026-07-25T01:00:00Z",
    updated_at: "2026-07-25T02:00:00Z",
  };
  vi.mocked(loadGovernanceQueues).mockResolvedValue({ facts: [], identityCases: [] });
  vi.mocked(loadEntityResolutionHistory).mockResolvedValue([approved]);
  vi.mocked(loadEntityResolutionImpact).mockResolvedValue({
    case: approved,
    source_reference_count: 3,
    candidate_reference_count: 7,
    source_trusted_identifier_count: 1,
    candidate_trusted_identifier_count: 2,
    recommended_canonical_entity_id: "entity-candidate",
    recommendation_reasons: ["verified_trusted_identifier_count", "governed_reference_count"],
    active_alias_entity_id: "entity-source",
    active_canonical_entity_id: "entity-candidate",
    rollback_available: true,
    references: [
      {
        domain: "target_intelligence",
        table: "target_profiles",
        column: "entity_id",
        source_count: 1,
        candidate_count: 2,
      },
    ],
    decisions: [
      {
        id: "decision-approve",
        action: "approve",
        decided_by_user_id: "reviewer-1",
        notes: "HGNC verified",
        snapshot: { canonical_entity_id: "entity-candidate" },
        created_at: "2026-07-25T02:00:00Z",
      },
    ],
  });
  vi.mocked(decideEntityResolution).mockResolvedValue({ ...approved, status: "reverted" });

  renderWithQueryClient(<GovernanceView />);
  fireEvent.click(await screen.findByRole("tab", { name: /实体消歧 0/ }));
  fireEvent.click(await screen.findByRole("tab", { name: /历史与回滚 1/ }));

  expect(await screen.findByRole("heading", { name: "跨域影响分析" })).toBeInTheDocument();
  expect(screen.getByText("target_profiles.entity_id")).toBeInTheDocument();
  expect(screen.getByText("不可变决策历史")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /拆分并恢复独立实体/ }));
  expect(screen.getByRole("alert")).toHaveTextContent("拆分恢复前必须填写依据");
  fireEvent.change(screen.getByRole("textbox", { name: "拆分恢复依据" }), {
    target: { value: "新证据确认两个靶点实体不等价" },
  });
  fireEvent.click(screen.getByRole("button", { name: /拆分并恢复独立实体/ }));

  await waitFor(() => expect(decideEntityResolution).toHaveBeenCalledOnce());
  expect(vi.mocked(decideEntityResolution).mock.calls[0]?.[0]).toEqual({
    caseId: "case-approved",
    action: "revert",
    expectedStatus: "approved",
    canonicalEntityId: null,
    notes: "新证据确认两个靶点实体不等价",
  });
});
