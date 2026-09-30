import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import {
  type CollectionPolicy,
  getWorkspaceExportPolicy,
  saveWorkspaceExportPolicy,
} from "../lib/contracts/collections";
import {
  executeCommercialOperation,
  loadCommercialRiskPage,
  loadCommercialWorkspace,
  loadLifecycleWorkspace,
} from "../lib/contracts/commercial";
import { CommercialView } from "../views/CommercialView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/commercial", () => ({
  commercialKeys: {
    root: ["commercial"],
    workspace: (deliveryFilter: string, disputeFilter: string) => [
      "commercial",
      "workspace",
      { deliveryFilter, disputeFilter },
    ],
    risks: (caseStatus: string, cursor: string | null) => ["commercial", "risks", { caseStatus, cursor }],
    lifecycle: ["commercial", "lifecycle"],
  },
  executeCommercialOperation: vi.fn(),
  loadCommercialRiskPage: vi.fn(),
  loadCommercialWorkspace: vi.fn(),
  loadLifecycleWorkspace: vi.fn(),
}));
vi.mock("../lib/contracts/collections", () => ({
  collectionsKeys: { policy: ["collections", "export-policy"] },
  getWorkspaceExportPolicy: vi.fn(),
  saveWorkspaceExportPolicy: vi.fn(),
}));

const overview = {
  as_of: "2026-07-16T04:00:00Z",
  open_risk_count: 1,
  period_start: "2026-07-16T00:00:00Z",
  subscriptions: [
    {
      subscription_id: "subscription-1",
      subscription_key: "enterprise-001",
      status: "active",
      client_key: "client-001",
      client_name: "Discovery Agent",
      billing_account_key: "account-001",
      billing_account_name: "Research",
      rate_card_key: "standard",
      rate_card_revision: 1,
      starts_at: "2026-07-01T00:00:00Z",
      ends_at: null,
      granted_units: "1000",
      consumed_units: "120",
      reserved_units: "20",
      available_units: "860",
      active_reservations: 1,
      daily_unique_records: 30,
      daily_usage: {
        settlement_count: 3,
        result_count: 40,
        unique_record_count: 30,
        new_unique_record_count: 30,
        response_bytes: 4096,
      },
      entitlements: [
        {
          key: "entities.read",
          max_result_rows: 100,
          daily_unit_limit: null,
          max_page_depth: 5,
          daily_unique_record_limit: 1000,
          max_response_bytes: 1000000,
          data_domains: ["entities"],
        },
      ],
    },
  ],
};

const clients = [
  {
    id: "client-id-1",
    client_key: "client-001",
    display_name: "Discovery Agent",
    active: true,
    subjects: [{ actor_type: "service", subject_id: "agent-1", active: true }],
    subscription_key: "enterprise-001",
    subscription_status: "active",
    billing_account_key: "account-001",
    available_units: "860",
    active_reservations: 1,
    denial_count_24h: 2,
    last_policy_event_at: "2026-07-16T03:00:00Z",
    created_at: "2026-07-01T00:00:00Z",
  },
];

const billingAccounts = [
  {
    id: "billing-account-1",
    account_key: "account-001",
    display_name: "Research",
    currency: "CNY",
    status: "active" as const,
    mapping_configured: false,
    external_customer_reference_masked: null,
    statement_count: 1,
    unresolved_statement_count: 1,
    invoice_count: 0,
    updated_at: "2026-07-16T03:00:00Z",
  },
];

const billingDeliveries = [
  {
    delivery_id: "billing-delivery-1",
    event_id: "billing-event-1",
    statement_id: "billing-statement-1",
    statement_key: "statement-2026-07",
    billing_account_id: "billing-account-1",
    billing_account_key: "account-001",
    billing_account_name: "Research",
    state: "dead" as const,
    attempts: 3,
    available_at: "2026-07-16T03:00:00Z",
    lease_expires_at: null,
    processed_at: null,
    last_error: "unknown provider customer",
    invoice_provider: null,
    external_invoice_id: null,
    invoice_status: null,
    created_at: "2026-07-16T02:00:00Z",
  },
];

const billingDisputes = [
  {
    id: "billing-dispute-1",
    dispute_key: "dispute.customer.0001",
    billing_account_id: "billing-account-1",
    billing_account_key: "account-001",
    billing_account_name: "Research",
    subscription_id: "subscription-1",
    statement_id: "billing-statement-1",
    statement_key: "statement-2026-07",
    invoice_reference_id: null,
    external_invoice_id: null,
    status: "open" as const,
    category: "usage" as const,
    disputed_units: "3.50000000",
    subject: "Unexpected usage charge",
    description: "Customer requests validation of metered searches.",
    opened_by: "finance-operator",
    opened_at: "2026-07-16T03:00:00Z",
    assigned_to: null,
    due_at: "2026-07-21T03:00:00Z",
    overdue: false,
    resolution_code: null,
    resolution_notes: "",
    resolved_by: null,
    resolved_at: null,
    resolution_adjustment_key: null,
    version: 1,
    created_at: "2026-07-16T03:00:00Z",
    updated_at: "2026-07-16T03:00:00Z",
  },
];

const exports = [
  {
    id: "export-id-1",
    dataset: "bioactivities",
    format: "jsonl",
    fields: ["id"],
    filters: {},
    max_records: 1000,
    record_count: 0,
    state: "pending_approval",
    approval_required: true,
    approved_by: null,
    approved_at: null,
    artifact_bytes: 0,
    artifact_sha256: null,
    license_attribution: "Internal licensed dataset",
    license_policy_sha256: "b".repeat(64),
    license_policy_version: "license-policy-v1",
    manifest_sha256: null,
    manifest_signature: null,
    manifest_key_id: null,
    failure_code: null,
    failure_message: null,
    requested_at: "2026-07-16T02:00:00Z",
    started_at: null,
    completed_at: null,
    expires_at: null,
  },
];

const risks = [
  {
    id: "risk-id-1",
    client_id: "client-id-1",
    client_key: "client-001",
    client_name: "Discovery Agent",
    actor_type: "service",
    subject_id: "agent-1",
    entitlement_key: "entities.read",
    phase: "reserve",
    reason_code: "cross_client_partition_limit_exceeded",
    query_sha256: "a".repeat(64),
    page_depth: 5,
    requested_records: 100,
    existing_unique_records: 900,
    projected_unique_records: 1000,
    request_id: "request-1",
    details: {},
    occurred_at: "2026-07-16T03:00:00Z",
    case_status: "open" as const,
    case_notes: "",
    reviewed_by: null,
    reviewed_at: null,
  },
];
const workspaceExportPolicy: CollectionPolicy = {
  id: "workspace-export-policy-1",
  policy_version: "workspace-export-v1",
  enabled: true,
  allowed_formats: ["csv", "json", "xlsx"],
  allowed_fields: ["position", "id", "entity_type", "name"],
  max_records_per_export: 20,
  attribution: "Internal licensed use",
  configured_by_user_id: "admin-1",
  policy_sha256: "c".repeat(64),
  created_at: "2026-07-16T03:00:00Z",
  updated_at: "2026-07-16T03:00:00Z",
};

beforeEach(() => {
  vi.mocked(loadCommercialWorkspace).mockResolvedValue({
    overview,
    clients,
    billingAccounts,
    billingDeliveries,
    billingDisputes,
    exports,
  });
  vi.mocked(loadCommercialRiskPage).mockResolvedValue({ items: risks, total_items: 1, next_cursor: null });
  vi.mocked(loadLifecycleWorkspace).mockResolvedValue({
    retentionPolicies: [],
    legalHolds: [],
    lifecycleEvents: [],
    purgeCandidates: [],
    sourcePurgeCandidates: [],
    deletedSourceAssets: [],
  });
  vi.mocked(executeCommercialOperation).mockResolvedValue({});
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(workspaceExportPolicy);
  vi.mocked(saveWorkspaceExportPolicy).mockResolvedValue({
    ...workspaceExportPolicy,
    policy_version: "workspace-export-v2",
  });
});

it("loads commercial metrics and all eight operations tabs", async () => {
  renderWithQueryClient(<CommercialView />);
  expect((await screen.findAllByText("860")).length).toBe(2);
  expect(screen.getByRole("tab", { name: "合同与额度" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Agent 客户端" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "账单投递" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "计费争议" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "数据导出" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "导出策略" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "风险事件" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "数据生命周期" })).toBeInTheDocument();
  expect(screen.getByText("enterprise-001")).toBeInTheDocument();
});

it("manages the external workbench export policy only from internal commercial operations", async () => {
  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "导出策略" }));

  expect(await screen.findByText("工作台导出策略")).toBeInTheDocument();
  expect(screen.getByText("当前版本 workspace-export-v1")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("策略版本"), { target: { value: "workspace-export-v2" } });
  fireEvent.change(screen.getByLabelText("单次导出上限"), { target: { value: "25" } });
  fireEvent.click(screen.getByRole("button", { name: "保存导出策略" }));

  await waitFor(() =>
    expect(saveWorkspaceExportPolicy).toHaveBeenCalledWith(
      expect.objectContaining({ policy_version: "workspace-export-v2", max_records_per_export: 25 }),
      expect.any(Object),
    ),
  );
  expect(await screen.findByRole("status")).toHaveTextContent("导出策略 workspace-export-v2 已生效");
});

it("keeps the client table structure visible for an empty tenant", async () => {
  vi.mocked(loadCommercialWorkspace).mockResolvedValue({
    overview: { ...overview, subscriptions: [] },
    clients: [],
    billingAccounts: [],
    billingDeliveries: [],
    billingDisputes: [],
    exports: [],
  });

  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "Agent 客户端" }));
  expect(screen.getByRole("columnheader", { name: "客户端" })).toBeInTheDocument();
  expect(screen.getByText("暂无 Agent 客户端")).toBeInTheDocument();
});

it("forwards operator filters through the generated commercial query contract", async () => {
  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "账单投递" }));
  fireEvent.change(screen.getByLabelText("投递状态"), { target: { value: "dead" } });

  await waitFor(() => expect(loadCommercialWorkspace).toHaveBeenLastCalledWith("dead", "all", expect.any(AbortSignal)));
});

it("loads the risk queue lazily and navigates signed cursor pages", async () => {
  const firstRisk = risks[0];
  if (!firstRisk) throw new Error("Expected the risk fixture to be populated");
  const secondRisk = {
    ...firstRisk,
    id: "risk-id-2",
    client_name: "Safety Agent",
    request_id: "request-2",
  };
  vi.mocked(loadCommercialRiskPage).mockImplementation(async (caseStatus, cursor) => {
    if (caseStatus === "open") return { items: risks, total_items: 1, next_cursor: null };
    return cursor
      ? { items: [secondRisk], total_items: 2, next_cursor: null }
      : { items: risks, total_items: 2, next_cursor: "signed-cursor-2" };
  });

  renderWithQueryClient(<CommercialView />);
  await screen.findByText("enterprise-001");
  expect(loadCommercialRiskPage).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("tab", { name: "风险事件" }));
  expect(await screen.findByText("cross_client_partition_limit_exceeded")).toBeInTheDocument();
  expect(loadCommercialRiskPage).toHaveBeenLastCalledWith("all", null, expect.any(AbortSignal));

  fireEvent.click(screen.getByRole("button", { name: "风险事件下一页" }));
  expect(await screen.findByText("Safety Agent")).toBeInTheDocument();
  expect(loadCommercialRiskPage).toHaveBeenLastCalledWith("all", "signed-cursor-2", expect.any(AbortSignal));
  expect(screen.getByRole("button", { name: "风险事件上一页" })).toBeEnabled();

  fireEvent.change(screen.getByLabelText("风险处置状态"), { target: { value: "open" } });
  await waitFor(() => expect(loadCommercialRiskPage).toHaveBeenLastCalledWith("open", null, expect.any(AbortSignal)));
  expect(screen.getByRole("button", { name: "风险事件上一页" })).toBeDisabled();
});

it("aborts an orphaned commercial query when the workbench unmounts", async () => {
  vi.mocked(loadCommercialWorkspace).mockImplementation(() => new Promise(() => undefined));
  const { unmount } = renderWithQueryClient(<CommercialView />);
  await waitFor(() => expect(loadCommercialWorkspace).toHaveBeenCalledOnce());
  const signal = vi.mocked(loadCommercialWorkspace).mock.calls[0]?.[2];
  expect(signal).toBeInstanceOf(AbortSignal);
  expect(signal?.aborted).toBe(false);

  unmount();

  await waitFor(() => expect(signal?.aborted).toBe(true));
});

it("surfaces query errors and allows an explicit operator retry", async () => {
  vi.mocked(loadCommercialWorkspace)
    .mockRejectedValueOnce(new Error("commercial service unavailable"))
    .mockResolvedValueOnce({
      overview,
      clients,
      billingAccounts,
      billingDeliveries,
      billingDisputes,
      exports,
    });
  renderWithQueryClient(<CommercialView />);
  expect(await screen.findByRole("alert")).toHaveTextContent("commercial service unavailable");

  fireEvent.click(screen.getByRole("button", { name: "重试" }));

  expect((await screen.findAllByText("860")).length).toBe(2);
  expect(loadCommercialWorkspace).toHaveBeenCalledTimes(2);
});

it("does not retry rejected commercial mutations implicitly", async () => {
  vi.mocked(executeCommercialOperation).mockRejectedValue(new Error("provider rejected the export"));
  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "数据导出" }));
  fireEvent.click(screen.getByRole("button", { name: "批准导出 export-id-1" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("provider rejected the export");
  expect(executeCommercialOperation).toHaveBeenCalledOnce();
});

it("creates and acknowledges a billing dispute from the human workbench", async () => {
  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "账单投递" }));
  fireEvent.click(screen.getByRole("button", { name: "对账期单 statement-2026-07 发起计费争议" }));
  fireEvent.change(screen.getByLabelText("争议额度"), { target: { value: "2.5" } });
  fireEvent.change(screen.getByLabelText("争议主题"), { target: { value: "Unexpected usage charge" } });
  fireEvent.change(screen.getByLabelText("争议说明"), { target: { value: "Please validate the metered searches." } });
  fireEvent.click(screen.getByRole("button", { name: "提交争议" }));
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "create-dispute",
      requestBody: expect.objectContaining({
        statement_id: "billing-statement-1",
        category: "usage",
        disputed_units: "2.5",
      }),
    }),
  );

  fireEvent.click(screen.getByRole("tab", { name: "计费争议" }));
  fireEvent.click(screen.getByRole("button", { name: "处理计费争议 dispute.customer.0001" }));
  fireEvent.change(screen.getByLabelText("争议处理记录"), {
    target: { value: "Finance accepted the case for investigation." },
  });
  fireEvent.click(screen.getByRole("button", { name: "提交处理" }));
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "transition-dispute",
      disputeId: "billing-dispute-1",
      requestBody: expect.objectContaining({ expected_version: 1, action: "investigate" }),
    }),
  );
});

it("requires reasons to map a provider customer and replay a dead billing delivery", async () => {
  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "账单投递" }));

  fireEvent.click(screen.getByRole("button", { name: "配置 Research 的 Provider 客户编号" }));
  const saveMapping = screen.getByRole("button", { name: "保存映射" });
  expect(saveMapping).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Provider 客户编号"), { target: { value: "ERP-CUSTOMER-1001" } });
  fireEvent.change(screen.getByLabelText("变更原因"), { target: { value: "approved by finance owner" } });
  fireEvent.click(saveMapping);
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "update-customer-mapping",
      accountId: "billing-account-1",
      requestBody: {
        external_customer_reference: "ERP-CUSTOMER-1001",
        reason: "approved by finance owner",
      },
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: "重放账期单 statement-2026-07" }));
  const replay = screen.getByRole("button", { name: "确认重放" });
  expect(replay).toBeDisabled();
  fireEvent.change(screen.getByLabelText("重放原因"), { target: { value: "provider mapping repaired" } });
  fireEvent.click(replay);
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "replay-delivery",
      deliveryId: "billing-delivery-1",
      requestBody: { reason: "provider mapping repaired" },
    }),
  );
});

it("requires an operator reason and revokes an agent client", async () => {
  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "Agent 客户端" }));
  fireEvent.click(screen.getByRole("button", { name: "停用 Discovery Agent" }));
  const submit = screen.getByRole("button", { name: "确认停用" });
  expect(submit).toBeDisabled();
  fireEvent.change(screen.getByLabelText("操作原因"), { target: { value: "credential compromise" } });
  fireEvent.click(submit);
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "update-client",
      clientId: "client-id-1",
      requestBody: { active: false, reason: "credential compromise" },
    }),
  );
});

it("approves exports and persists a risk review", async () => {
  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "数据导出" }));
  fireEvent.click(screen.getByRole("button", { name: "批准导出 export-id-1" }));
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "act-on-export",
      jobId: "export-id-1",
      action: "approve",
    }),
  );

  fireEvent.click(screen.getByRole("tab", { name: "风险事件" }));
  fireEvent.click(await screen.findByRole("button", { name: "处置风险事件 Discovery Agent" }));
  fireEvent.change(screen.getByLabelText("处置记录"), { target: { value: "client contacted" } });
  fireEvent.click(screen.getByRole("button", { name: "提交处置" }));
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "review-risk",
      eventId: "risk-id-1",
      requestBody: { status: "acknowledged", notes: "client contacted" },
    }),
  );
});

it("governs retention, legal holds, and verified purge from the lifecycle tab", async () => {
  const policy = {
    id: "retention-policy-1",
    data_class: "commercial_export_artifact" as const,
    policy_version: 2,
    retention_seconds: 129600,
    legal_basis: "enterprise retention schedule",
    geographic_scope: ["CN"],
    active: true,
    configured_by_user_id: "admin-1",
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-16T00:00:00Z",
  };
  const sourcePolicy = {
    ...policy,
    id: "retention-policy-source-1",
    data_class: "source_asset_snapshot" as const,
    retention_seconds: 2592000,
    legal_basis: "approved source withdrawal schedule",
  };
  const hold = {
    id: "legal-hold-1",
    scope_type: "tenant" as const,
    scope_id: null,
    matter_reference: "MATTER-001",
    reason: "Preserve evidence",
    status: "active" as const,
    placed_by_user_id: "admin-1",
    placed_at: "2026-07-16T00:00:00Z",
    released_by_user_id: null,
    released_at: null,
    release_reason: null,
  };
  const lifecycleEvent = {
    id: "lifecycle-event-1",
    data_class: "commercial_export_artifact",
    target_type: "data_export_job",
    target_id: "export-old-1",
    action: "blocked" as const,
    outcome: "blocked" as const,
    idempotency_key: "purge-old-1",
    policy_id: policy.id,
    policy_version: 2,
    legal_hold_ids: [hold.id],
    actor_user_id: "admin-1",
    reason: "scheduled sweep",
    details: {},
    created_at: "2026-07-16T01:00:00Z",
  };
  const candidate = {
    ...exports[0],
    id: "export-expired-1",
    state: "completed",
    artifact_bytes: 1024,
    completed_at: "2026-07-14T00:00:00Z",
    expires_at: "2026-07-15T00:00:00Z",
  };
  const sourceCandidate = {
    id: "source-asset-missing-1",
    data_source_id: "data-source-1",
    logical_path: "literature/egfr.md",
    file_name: "egfr.md",
    state: "missing",
    missing_since: "2026-06-01T00:00:00Z",
    retention_eligible: true,
    version_count: 2,
    raw_object_count: 2,
    extracted_object_count: 2,
    extraction_run_count: 1,
    staged_fact_count: 1,
    published_fact_count: 0,
    evidence_claim_count: 0,
    knowledge_citation_count: 0,
    retrieval_projection_count: 1,
    shared_document_count: 0,
    other_document_reference_count: 0,
    blockers: [],
  };
  const deletedSourceAsset = {
    id: "source-asset-deleted-1",
    data_source_id: "data-source-1",
    logical_path: "literature/withdrawn-egfr.md",
    file_name: "withdrawn-egfr.md",
    state: "deleted" as const,
    updated_at: "2026-07-16T02:00:00Z",
  };
  vi.mocked(loadLifecycleWorkspace).mockResolvedValue({
    retentionPolicies: [policy, sourcePolicy],
    legalHolds: [hold],
    lifecycleEvents: [lifecycleEvent],
    purgeCandidates: [candidate],
    sourcePurgeCandidates: [sourceCandidate],
    deletedSourceAssets: [deletedSourceAsset],
  });

  renderWithQueryClient(<CommercialView />);
  fireEvent.click(await screen.findByRole("tab", { name: "数据生命周期" }));
  expect(await screen.findByText("导出对象保留策略")).toBeInTheDocument();
  expect(screen.getByText("MATTER-001")).toBeInTheDocument();
  expect(screen.getByText("export-expired-1")).toBeInTheDocument();
  expect(screen.getByText("egfr.md")).toBeInTheDocument();
  expect(screen.getByText("withdrawn-egfr.md")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText("保留时长（小时）")).toHaveValue(36));

  fireEvent.change(screen.getByLabelText("保留时长（小时）"), { target: { value: "48" } });
  fireEvent.change(screen.getByRole("textbox", { name: /^法律与合同依据$/ }), {
    target: { value: "enterprise retention schedule revision" },
  });
  const savePolicy = screen.getAllByRole("button", { name: "保存策略" })[0];
  expect(savePolicy).toBeEnabled();
  fireEvent.submit(savePolicy.closest("form") as HTMLFormElement);
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "save-retention-policy",
      dataClass: "commercial_export_artifact",
      requestBody: expect.objectContaining({ retention_seconds: 172800, active: true }),
    }),
  );

  fireEvent.change(screen.getByLabelText("源资料保留时长（小时）"), { target: { value: "1440" } });
  fireEvent.change(screen.getByLabelText("源资料法律与合同依据"), {
    target: { value: "source schedule revision" },
  });
  fireEvent.submit(screen.getAllByRole("button", { name: "保存策略" })[1].closest("form") as HTMLFormElement);
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "save-retention-policy",
      dataClass: "source_asset_snapshot",
      requestBody: expect.objectContaining({ retention_seconds: 5184000, active: true }),
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: "解除法律保全 MATTER-001" }));
  fireEvent.change(screen.getByLabelText("生命周期操作原因"), { target: { value: "matter closed" } });
  fireEvent.click(screen.getByRole("button", { name: "确认执行" }));
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "release-legal-hold",
      holdId: "legal-hold-1",
      requestBody: { reason: "matter closed" },
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: "清除到期对象 export-expired-1" }));
  fireEvent.change(screen.getByLabelText("生命周期操作原因"), { target: { value: "retention period ended" } });
  fireEvent.click(screen.getByRole("button", { name: "确认执行" }));
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "purge-export",
      jobId: "export-expired-1",
      requestBody: {
        idempotency_key: expect.stringMatching(/^web\.purge\./),
        reason: "retention period ended",
      },
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: "撤回源资料 egfr.md" }));
  fireEvent.change(screen.getByLabelText("生命周期操作原因"), { target: { value: "source retention period ended" } });
  fireEvent.click(screen.getByRole("button", { name: "确认执行" }));
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "purge-source",
      assetId: "source-asset-missing-1",
      requestBody: {
        idempotency_key: expect.stringMatching(/^web\.source-purge\./),
        reason: "source retention period ended",
      },
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: "重新授权源资料 withdrawn-egfr.md" }));
  fireEvent.change(screen.getByLabelText("生命周期操作原因"), {
    target: { value: "source rights restored" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认执行" }));
  await waitFor(() =>
    expect(executeCommercialOperation).toHaveBeenCalledWith({
      kind: "reauthorize-source",
      assetId: "source-asset-deleted-1",
      requestBody: {
        idempotency_key: expect.stringMatching(/^web\.source-reauthorize\./),
        reason: "source rights restored",
      },
    }),
  );
});
