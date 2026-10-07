import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import {
  cancelIngestionRun,
  createDataSource,
  decideQuarantineCase,
  loadDataFactory,
  loadIngestionFindings,
  loadQuarantineCase,
  loadSearchProjectionStatus,
  loadSourceAsset,
  loadSourceAssets,
  loadSourceVersionPreview,
  replayIngestionRun,
  replaySourceVersion,
  updateDataSource,
} from "../lib/contracts/dataFactory";
import type { DataSource, User } from "../lib/types";
import { DataFactoryView } from "../views/DataFactoryView";
import { renderWithQueryClient } from "./renderWithQueryClient";

async function verifyDialogKeyboard(opener: HTMLElement, title: string | RegExp) {
  opener.focus();
  fireEvent.click(opener);
  const dialog = await screen.findByRole("dialog", { name: title });
  await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: title })).not.toBeInTheDocument();
  await waitFor(() => expect(opener).toHaveFocus());
  fireEvent.click(opener);
  await waitFor(() => expect(screen.getByRole("dialog", { name: title }).contains(document.activeElement)).toBe(true));
}

vi.mock("../lib/contracts/dataFactory", () => ({
  dataFactoryKeys: {
    all: ["data-factory"],
    searchStatus: ["data-factory", "search-status"],
    findings: (runId: string) => ["data-factory", "findings", runId],
    asset: (assetId: string) => ["data-factory", "asset", assetId],
    preview: (versionId: string) => ["data-factory", "preview", versionId],
    quarantine: (versionId: string) => ["data-factory", "quarantine", versionId],
  },
  loadDataFactory: vi.fn(),
  loadIngestionFindings: vi.fn(),
  loadSourceAsset: vi.fn(),
  loadSourceAssets: vi.fn(),
  loadSourceVersionPreview: vi.fn(),
  loadQuarantineCase: vi.fn(),
  loadSearchProjectionStatus: vi.fn(),
  decideQuarantineCase: vi.fn(),
  replayIngestionRun: vi.fn(),
  replaySourceVersion: vi.fn(),
  cancelIngestionRun: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  triggerDataSourceScan: vi.fn(),
  updateDataSourceState: vi.fn(),
}));

const user: User = {
  id: "admin-1",
  tenant_id: "tenant-1",
  email: "admin@example.test",
  display_name: "Administrator",
  role: "admin",
};

const source: DataSource = {
  id: "source-1",
  name: "Legacy literature",
  source_type: "folder",
  root_uri: "/sources/knowledge/literature",
  credential_configured: false,
  owner: "migration-unassigned",
  data_classification: "internal",
  authorization_scopes: [],
  authorization_valid_from: "2026-01-01T00:00:00Z",
  authorization_valid_until: "2026-12-31T00:00:00Z",
  dataset_key: "literature",
  include_globs: ["*", "**/*"],
  exclude_globs: [],
  routing_rules: [],
  stable_seconds: 30,
  max_file_bytes: 1073741824,
  scan_interval_seconds: 300,
  expected_freshness_seconds: 86400,
  rate_limit_per_minute: 60,
  config_version: 1,
  state: "active",
  last_scanned_at: null,
  last_success_at: null,
  unavailable_since: null,
  consecutive_failures: 0,
  last_error: null,
  last_cursor_at: null,
};

beforeEach(() => {
  vi.mocked(createDataSource).mockReset();
  vi.mocked(decideQuarantineCase).mockReset();
  vi.mocked(updateDataSource).mockReset();
  vi.mocked(replayIngestionRun).mockReset();
  vi.mocked(replaySourceVersion).mockReset();
  vi.mocked(cancelIngestionRun).mockReset();
  vi.mocked(loadSourceAsset).mockReset();
  vi.mocked(loadSourceAssets).mockReset();
  vi.mocked(loadSourceVersionPreview).mockReset();
  vi.mocked(loadQuarantineCase).mockReset();
  vi.mocked(loadSearchProjectionStatus).mockReset();
  vi.mocked(loadDataFactory).mockResolvedValue({
    capabilities: {
      automatic_scheduling_enabled: true,
      durable_workflows_enabled: true,
      isolated_parser_enabled: true,
      malware_scanning_enabled: true,
      ai_governance_enabled: true,
      deterministic_governance_enabled: true,
      ai_model_configured: true,
      ai_model: "governed-extractor",
      ai_auto_publish_threshold: 0.95,
      allowed_folder_roots: ["/sources/knowledge"],
      parseable_extensions: [".pdf", ".docx"],
      asset_only_extensions: [".cdx"],
    },
    sources: [source],
    runs: [],
    datasets: [
      {
        dataset_key: "literature",
        display_name: "Licensed Literature",
        active: true,
        license_id: "license-2026",
        license_policy_version: "v3",
        permitted_channels: ["web", "mcp"],
        license_current: true,
        attribution: "Licensed test source",
      },
    ],
    readiness: [
      {
        source_id: "source-1",
        configuration_ready: false,
        operational_status: "blocked",
        connector_id: "folder-v1",
        incremental: true,
        replayable: true,
        delivery_channels: ["web", "mcp"],
        cursor_present: false,
        last_cursor_at: null,
        freshness_age_seconds: null,
        checks: [{ code: "owner", status: "fail", message: "A named accountable data owner is required" }],
      },
    ],
    quarantineCases: [],
  });
  vi.mocked(loadSourceAssets).mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
  vi.mocked(loadSearchProjectionStatus).mockResolvedValue({
    available: true,
    version: "3.7.0",
    cluster_name: "pharma-search",
    cluster_status: "green",
    aliases: { pharma_entities_read: ["pharma_entities_v2"] },
    deliveries: { pending: 2, failed: 1, succeeded: 30 },
    error: null,
  });
});

it("does not block the data factory on a slow search projection status request", async () => {
  vi.mocked(loadSearchProjectionStatus).mockImplementation(() => new Promise(() => undefined));

  renderWithQueryClient(<DataFactoryView user={user} />);

  expect(await screen.findByRole("button", { name: "接入自动数据源" })).toBeInTheDocument();
  expect(loadSearchProjectionStatus).toHaveBeenCalledOnce();
});

it("refreshes source assets together with the data factory snapshot", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  const refresh = await screen.findByRole("button", { name: "刷新数据工厂" });
  await waitFor(() => expect(loadSourceAssets).toHaveBeenCalledOnce());
  fireEvent.click(refresh);

  await waitFor(() => expect(loadSourceAssets).toHaveBeenCalledTimes(2));
});

it("selects the matching governed dataset when a public source type changes", async () => {
  const snapshot = await loadDataFactory();
  vi.mocked(loadDataFactory).mockResolvedValue({
    ...snapshot,
    datasets: [
      {
        dataset_key: "clinical_trials",
        display_name: "Clinical Trials",
        active: true,
        license_id: "clinical-license",
        license_policy_version: "v1",
        permitted_channels: ["web", "mcp"],
        license_current: true,
        attribution: "ClinicalTrials.gov",
      },
      ...snapshot.datasets,
    ],
  });

  renderWithQueryClient(<DataFactoryView user={user} />);
  fireEvent.click(await screen.findByRole("button", { name: "接入自动数据源" }));
  fireEvent.change(screen.getByLabelText("数据源类型"), { target: { value: "pubmed" } });

  expect(screen.getByLabelText("目标数据集")).toHaveValue("literature");
});

it("identifies governed inference as a third-party remote API", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  expect(await screen.findByText("第三方 LLM API")).toBeInTheDocument();
  expect(screen.getByText("远程 API 已启用")).toBeInTheDocument();
  expect(screen.getByText("远程 API · governed-extractor")).toBeInTheDocument();
  expect(screen.getByText("结构化治理")).toBeInTheDocument();
  expect(screen.getByText("官方结构化来源可直接校验")).toBeInTheDocument();
});

it("disables scans and localizes readiness guidance when durable workflows are unavailable", async () => {
  const snapshot = await loadDataFactory();
  vi.mocked(loadDataFactory).mockResolvedValue({
    ...snapshot,
    capabilities: {
      ...snapshot.capabilities,
      automatic_scheduling_enabled: false,
      durable_workflows_enabled: false,
    },
    readiness: [
      {
        ...snapshot.readiness[0],
        configuration_ready: true,
        operational_status: "pending",
        checks: [
          {
            code: "freshness",
            status: "warn",
            message: "Source has not completed its first scan",
          },
        ],
      },
    ],
  });

  renderWithQueryClient(<DataFactoryView user={user} />);

  const scan = await screen.findByRole("button", { name: "立即扫描 Legacy literature" });
  expect(scan).toBeDisabled();
  expect(scan).toHaveAttribute("title", "自动扫描工作流尚未启用");
  expect(screen.getByText("尚未完成首次扫描")).toBeInTheDocument();
  expect(screen.getByText("自动扫描工作流尚未启用；完成平台运行配置后才能执行扫描。")).toBeInTheDocument();
  expect(screen.queryByText("Source has not completed its first scan")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "接入自动数据源" }));
  expect(screen.getByText("数据源登记后将在工作流服务启用时进入自动调度")).toBeInTheDocument();
});

it("requires an audited decision and keeps malware rescans behind ClamAV", async () => {
  const snapshot = await loadDataFactory();
  const quarantineCase = {
    source_version_id: "version-quarantine-1",
    source_asset_id: "asset-quarantine-1",
    file_name: "suspected-egfr.md",
    logical_path: "incoming/suspected-egfr.md",
    quarantine_status: "pending_review" as const,
    quarantine_version: 1,
    threat_name: "Win.Test.EICAR_HDB-1",
    error_code: "malware_detected",
    error_message: "Malware scanner detected a threat",
    updated_at: "2026-07-25T08:00:00Z",
    decisions: [
      {
        id: "decision-scan-1",
        source_version_id: "version-quarantine-1",
        action: "scan_detected",
        expected_version: 0,
        resulting_version: 1,
        previous_status: "not_applicable" as const,
        resulting_status: "pending_review" as const,
        reason: "Malware scanner detection requires operator review",
        actor_type: "system",
        actor_id: "data-factory",
        workflow_id: null,
        details: { threat_name: "Win.Test.EICAR_HDB-1" },
        created_at: "2026-07-25T08:00:00Z",
      },
    ],
  };
  vi.mocked(loadDataFactory).mockResolvedValue({
    ...snapshot,
    quarantineCases: [quarantineCase],
  });
  vi.mocked(loadQuarantineCase).mockResolvedValue(quarantineCase);
  let resolveDecision!: (result: Awaited<ReturnType<typeof decideQuarantineCase>>) => void;
  const decision = new Promise<Awaited<ReturnType<typeof decideQuarantineCase>>>((resolve) => {
    resolveDecision = resolve;
  });
  vi.mocked(decideQuarantineCase).mockReturnValue(decision);
  const acceptedDecision: Awaited<ReturnType<typeof decideQuarantineCase>> = {
    decision_id: "decision-rescan-1",
    source_version_id: quarantineCase.source_version_id,
    action: "rescan",
    quarantine_status: "rescan_requested",
    quarantine_version: 2,
    workflow_id: "source-version-reprocess-version-quarantine-1",
    status: "accepted",
  };

  renderWithQueryClient(<DataFactoryView user={user} />);

  expect(await screen.findByLabelText("1 个待处置案件")).toBeInTheDocument();
  expect(screen.getByText("Win.Test.EICAR_HDB-1")).toBeInTheDocument();
  await verifyDialogKeyboard(screen.getByRole("button", { name: "处置" }), "隔离案件处置");
  expect(await screen.findByRole("dialog", { name: "隔离案件处置" })).toBeInTheDocument();
  expect(await screen.findByText(/仍强制经过 ClamAV/)).toBeInTheDocument();
  expect(screen.getByText("扫描发现威胁")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("处置动作"), { target: { value: "rescan" } });
  const confirm = screen.getByRole("button", { name: "提交处置" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("处置原因"), {
    target: { value: "Updated signatures require a complete controlled rescan" },
  });
  fireEvent.click(confirm);

  await waitFor(() =>
    expect(decideQuarantineCase).toHaveBeenCalledWith(quarantineCase.source_version_id, {
      operation_key: expect.stringMatching(/^quarantine-decision:/),
      expected_version: 1,
      action: "rescan",
      reason: "Updated signatures require a complete controlled rescan",
    }),
  );
  expect(screen.getByLabelText("处置动作")).toBeDisabled();
  expect(screen.getByLabelText("处置原因")).toBeDisabled();
  expect(screen.getByRole("dialog", { name: "隔离案件处置" })).toHaveAttribute("aria-busy", "true");
  const pendingDialog = screen.getByRole("dialog", { name: "隔离案件处置" });
  expect(within(pendingDialog).getByRole("status")).toHaveTextContent("正在提交隔离处置");
  fireEvent.keyDown(document, { key: "Escape" });
  const pendingForm = pendingDialog.querySelector("form");
  if (!pendingForm) throw new Error("Expected a quarantine decision form");
  fireEvent.submit(pendingForm);
  expect(decideQuarantineCase).toHaveBeenCalledOnce();
  await act(async () => resolveDecision(acceptedDecision));
  expect(await screen.findByText(/复扫工作流已提交/)).toBeInTheDocument();
});

it("moves focus into the data source dialog and restores it to the opener", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  const opener = await screen.findByRole("button", { name: "接入自动数据源" });
  opener.focus();
  fireEvent.click(opener);

  const dialog = screen.getByRole("dialog", { name: "接入自动数据源" });
  const nameInput = screen.getByLabelText("数据源名称");
  await waitFor(() => expect(nameInput).toHaveFocus());
  expect(dialog).toContainElement(document.activeElement as HTMLElement);

  fireEvent.click(screen.getByRole("button", { name: "关闭" }));
  await waitFor(() => expect(dialog).not.toBeInTheDocument());
  await waitFor(() => expect(opener).toHaveFocus());
});

it("shows blocked source governance and registers only against a licensed dataset", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  expect(await screen.findByText("请指定可追责的数据负责人")).toBeInTheDocument();
  expect(screen.getByText("folder-v1")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "检索投影运行状态" })).toBeInTheDocument();
  expect(screen.getByText("pharma-search")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "接入自动数据源" }));

  fireEvent.change(screen.getByLabelText("数据源名称"), { target: { value: "New literature" } });
  fireEvent.change(screen.getByLabelText("数据负责人"), { target: { value: "Clinical Intelligence" } });
  fireEvent.change(screen.getByLabelText("授权范围编号（每行一个）"), {
    target: { value: "contract:licensed-2026\npolicy:internal-rd" },
  });
  expect(screen.getByRole("option", { name: "Licensed Literature · license-2026/v3" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "注册" }));

  await waitFor(() => expect(createDataSource).toHaveBeenCalledOnce());
  expect(createDataSource).toHaveBeenCalledWith(
    expect.objectContaining({
      owner: "Clinical Intelligence",
      authorization_scopes: ["contract:licensed-2026", "policy:internal-rd"],
      authorization_valid_from: expect.any(String),
      authorization_valid_until: null,
      dataset_key: "literature",
    }),
  );
});

it("paginates ingestion runs so the management workbench stays bounded", async () => {
  const snapshot = await loadDataFactory();
  vi.mocked(loadDataFactory).mockResolvedValue({
    ...snapshot,
    runs: Array.from({ length: 26 }, (_, index) => ({
      id: `run-${index}`,
      data_source_id: source.id,
      workflow_id: `workflow-${index}`,
      temporal_workflow_id: `source-ingest-${source.id}`,
      temporal_run_id: `temporal-${index}`,
      state: "succeeded" as const,
      effective_state: "succeeded" as const,
      cancel_requested_at: null,
      cancelable: false,
      progress_percent: 100,
      total_versions: index,
      completed_versions: index,
      stages: [],
      counters: { discovered: index },
      result: {},
      created_at: `2026-07-20T00:${String(index).padStart(2, "0")}:00Z`,
      started_at: null,
      heartbeat_at: null,
      completed_at: null,
      error_summary: null,
    })),
  });

  renderWithQueryClient(<DataFactoryView user={user} />);

  expect(await screen.findByText("第 1 / 2 页，共 26 条")).toBeInTheDocument();
  expect(screen.getByText("workflow-24")).toBeInTheDocument();
  expect(screen.queryByText("workflow-25")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "入库运行记录下一页" }));
  expect(screen.getByText("workflow-25")).toBeInTheDocument();
  expect(screen.queryByText("workflow-24")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "入库运行记录下一页" })).toBeDisabled();
});

it("requires an operator reason before replaying a terminal ingestion run", async () => {
  const snapshot = await loadDataFactory();
  const failedRun = {
    id: "run-failed",
    data_source_id: source.id,
    workflow_id: "workflow-failed",
    temporal_workflow_id: `source-ingest-${source.id}`,
    temporal_run_id: "temporal-failed",
    state: "failed" as const,
    effective_state: "failed" as const,
    cancel_requested_at: null,
    cancelable: false,
    progress_percent: 50,
    total_versions: 1,
    completed_versions: 1,
    stages: [],
    counters: { failed: 1 },
    result: {},
    created_at: "2026-07-20T00:00:00Z",
    started_at: "2026-07-20T00:00:01Z",
    heartbeat_at: "2026-07-20T00:01:00Z",
    completed_at: "2026-07-20T00:01:00Z",
    error_summary: "Parser service unavailable",
  };
  vi.mocked(loadDataFactory).mockResolvedValue({ ...snapshot, runs: [failedRun] });
  vi.mocked(replayIngestionRun).mockResolvedValue({
    workflow_id: `source-ingest-${source.id}`,
    ingestion_run_id: `source-ingest-${source.id}-next`,
    status: "accepted",
    replayed_from_run_id: failedRun.id,
  });

  renderWithQueryClient(<DataFactoryView user={user} />);

  await verifyDialogKeyboard(await screen.findByRole("button", { name: "重放 workflow-failed" }), "重放入库运行");
  const confirm = screen.getByRole("button", { name: "确认重放" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("重放原因"), {
    target: { value: "Parser service recovered after maintenance" },
  });
  expect(confirm).toBeEnabled();
  fireEvent.click(confirm);

  await waitFor(() =>
    expect(replayIngestionRun).toHaveBeenCalledWith(
      failedRun.id,
      expect.stringMatching(/^ingestion-replay:run-failed:/),
      "failed",
      "Parser service recovered after maintenance",
    ),
  );
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "重放入库运行" })).not.toBeInTheDocument());
});

it("explains a failed stage when the run has no finding payload or error summary", async () => {
  const snapshot = await loadDataFactory();
  const failedRun = {
    id: "run-failed-stage",
    data_source_id: source.id,
    workflow_id: "workflow-failed-stage",
    temporal_workflow_id: `source-ingest-${source.id}`,
    temporal_run_id: "temporal-failed-stage",
    state: "failed" as const,
    effective_state: "failed" as const,
    cancel_requested_at: null,
    cancelable: false,
    progress_percent: 100,
    total_versions: 1,
    completed_versions: 1,
    stages: [
      {
        stage: "discovery" as const,
        status: "succeeded" as const,
        completed_items: 1,
        failed_items: 0,
        total_items: 1,
      },
      {
        stage: "snapshot" as const,
        status: "succeeded" as const,
        completed_items: 1,
        failed_items: 0,
        total_items: 1,
      },
      {
        stage: "malware_scan" as const,
        status: "failed" as const,
        completed_items: 0,
        failed_items: 1,
        total_items: 1,
      },
      {
        stage: "parse" as const,
        status: "not_started" as const,
        completed_items: 0,
        failed_items: 0,
        total_items: 1,
      },
      {
        stage: "retrieval" as const,
        status: "not_started" as const,
        completed_items: 0,
        failed_items: 0,
        total_items: 1,
      },
      {
        stage: "governance" as const,
        status: "not_started" as const,
        completed_items: 0,
        failed_items: 0,
        total_items: 1,
      },
    ],
    counters: { discovered: 1 },
    result: {},
    created_at: "2026-07-20T00:00:00Z",
    started_at: "2026-07-20T00:00:01Z",
    heartbeat_at: "2026-07-20T00:01:00Z",
    completed_at: "2026-07-20T00:01:00Z",
    error_summary: null,
  };
  vi.mocked(loadDataFactory).mockResolvedValue({ ...snapshot, runs: [failedRun] });
  vi.mocked(loadIngestionFindings).mockResolvedValue([]);

  renderWithQueryClient(<DataFactoryView user={user} />);

  fireEvent.click(await screen.findByRole("button", { name: "运行详情" }));
  expect(await screen.findByText(/运行在安全扫描阶段失败，未生成发现项/)).toBeInTheDocument();
  expect(screen.queryByText("该运行没有发现项")).not.toBeInTheDocument();
});

it("shows the real stage graph and requires a reason before canceling an active Temporal execution", async () => {
  const snapshot = await loadDataFactory();
  const runningRun = {
    id: "run-active",
    data_source_id: source.id,
    workflow_id: "workflow-active-correlation",
    temporal_workflow_id: `source-ingest-${source.id}`,
    temporal_run_id: "temporal-active",
    state: "succeeded" as const,
    effective_state: "running" as const,
    cancel_requested_at: null,
    cancelable: true,
    progress_percent: 58,
    total_versions: 2,
    completed_versions: 1,
    stages: [
      {
        stage: "discovery" as const,
        status: "succeeded" as const,
        completed_items: 1,
        failed_items: 0,
        total_items: 1,
      },
      { stage: "snapshot" as const, status: "succeeded" as const, completed_items: 2, failed_items: 0, total_items: 2 },
      {
        stage: "malware_scan" as const,
        status: "succeeded" as const,
        completed_items: 2,
        failed_items: 0,
        total_items: 2,
      },
      { stage: "parse" as const, status: "running" as const, completed_items: 1, failed_items: 0, total_items: 2 },
      {
        stage: "retrieval" as const,
        status: "not_started" as const,
        completed_items: 0,
        failed_items: 0,
        total_items: 2,
      },
      {
        stage: "governance" as const,
        status: "not_started" as const,
        completed_items: 0,
        failed_items: 0,
        total_items: 2,
      },
    ],
    counters: { discovered: 2 },
    result: {},
    created_at: "2026-07-20T00:00:00Z",
    started_at: "2026-07-20T00:00:01Z",
    heartbeat_at: "2026-07-20T00:01:00Z",
    completed_at: null,
    error_summary: null,
  };
  vi.mocked(loadDataFactory).mockResolvedValue({ ...snapshot, runs: [runningRun] });
  vi.mocked(cancelIngestionRun).mockResolvedValue({
    run_id: runningRun.id,
    workflow_id: runningRun.workflow_id,
    temporal_workflow_id: runningRun.temporal_workflow_id,
    temporal_run_id: runningRun.temporal_run_id,
    status: "cancel_requested",
  });

  renderWithQueryClient(<DataFactoryView user={user} />);

  expect(await screen.findByText("58%")).toBeInTheDocument();
  await verifyDialogKeyboard(screen.getByRole("button", { name: "运行详情" }), "运行发现项");
  expect(screen.getByRole("heading", { name: "逐阶段运行图" })).toBeInTheDocument();
  expect(screen.getByText("1 完成 / 0 失败 / 2 总计")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "关闭" }));
  await verifyDialogKeyboard(screen.getByRole("button", { name: "取消 workflow-active-correlation" }), "取消入库运行");
  const confirm = screen.getByRole("button", { name: "确认取消" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("取消原因"), {
    target: { value: "Source owner requested a controlled stop" },
  });
  fireEvent.click(confirm);

  await waitFor(() =>
    expect(cancelIngestionRun).toHaveBeenCalledWith(
      runningRun.id,
      expect.stringMatching(/^ingestion-cancel:run-active:/),
      "Source owner requested a controlled stop",
    ),
  );
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "取消入库运行" })).not.toBeInTheDocument());
});

it("explains a completed discovery with no new versions without implying version completion", async () => {
  const snapshot = await loadDataFactory();
  const noVersionRun = {
    id: "run-no-new-version",
    data_source_id: source.id,
    workflow_id: "workflow-no-new-version",
    temporal_workflow_id: "source-ingest-no-new-version",
    temporal_run_id: "temporal-no-new-version",
    state: "succeeded" as const,
    effective_state: "succeeded" as const,
    cancel_requested_at: null,
    cancelable: false,
    progress_percent: 100,
    total_versions: 0,
    completed_versions: 0,
    stages: [
      {
        stage: "discovery" as const,
        status: "succeeded" as const,
        completed_items: 1,
        failed_items: 0,
        total_items: 1,
      },
      { stage: "snapshot" as const, status: "skipped" as const, completed_items: 0, failed_items: 0, total_items: 0 },
      {
        stage: "malware_scan" as const,
        status: "skipped" as const,
        completed_items: 0,
        failed_items: 0,
        total_items: 0,
      },
      { stage: "parse" as const, status: "skipped" as const, completed_items: 0, failed_items: 0, total_items: 0 },
      { stage: "retrieval" as const, status: "skipped" as const, completed_items: 0, failed_items: 0, total_items: 0 },
      { stage: "governance" as const, status: "skipped" as const, completed_items: 0, failed_items: 0, total_items: 0 },
    ],
    counters: { discovered: 1 },
    result: {},
    created_at: "2026-07-20T00:00:00Z",
    started_at: "2026-07-20T00:00:01Z",
    heartbeat_at: "2026-07-20T00:01:00Z",
    completed_at: "2026-07-20T00:01:00Z",
    error_summary: null,
  };
  vi.mocked(loadDataFactory).mockResolvedValue({ ...snapshot, runs: [noVersionRun] });
  vi.mocked(loadIngestionFindings).mockResolvedValue([]);

  renderWithQueryClient(<DataFactoryView user={user} />);

  expect(await screen.findAllByText("已检查 1 个对象 · 本次无新增版本")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "运行详情" }));
  expect(screen.getByText("总进度 100% · 已检查 1 个对象 · 本次无新增版本")).toBeInTheDocument();
  expect(screen.queryByText("0/0 个版本完成")).not.toBeInTheDocument();
});

it("opens immutable source versions and previews only parsed text", async () => {
  const snapshot = await loadDataFactory();
  const asset = {
    id: "asset-1",
    data_source_id: source.id,
    logical_path: "reports/egfr.pdf",
    source_uri: "file:///sources/reports/egfr.pdf",
    file_name: "egfr.pdf",
    extension: ".pdf",
    media_type: "application/pdf",
    processing_mode: "parse",
    state: "active" as const,
    current_version_id: "version-2",
    first_seen_at: "2026-07-20T00:00:00Z",
    last_seen_at: "2026-07-21T00:00:00Z",
    missing_since: null,
  };
  const versions = [
    {
      id: "version-2",
      source_asset_id: asset.id,
      version_number: 2,
      content_sha256: "c".repeat(64),
      size_bytes: 2048,
      source_modified_at: "2026-07-21T00:00:00Z",
      discovered_at: "2026-07-21T00:00:00Z",
      state: "failed" as const,
      snapshot_status: "succeeded" as const,
      malware_scan_status: "succeeded" as const,
      parse_status: "failed" as const,
      retrieval_status: "not_started" as const,
      governance_status: "not_started" as const,
      malware_scanner: "clamav",
      malware_signature_version: "1",
      malware_scanned_at: "2026-07-21T00:01:00Z",
      quarantine_status: "not_applicable" as const,
      quarantine_version: 0,
      quarantine_updated_at: null,
      extracted_text_sha256: null,
      parser_name: null,
      parser_version: null,
      metadata_json: { malware_scan: { status: "clean" } },
      error_code: "parse_failed",
      error_message: "Parser rejected the document",
      replayable_stages: ["malware_scan" as const, "parse" as const],
    },
    {
      id: "version-1",
      source_asset_id: asset.id,
      version_number: 1,
      content_sha256: "a".repeat(64),
      size_bytes: 1024,
      source_modified_at: "2026-07-20T00:00:00Z",
      discovered_at: "2026-07-20T00:00:00Z",
      state: "parsed" as const,
      snapshot_status: "succeeded" as const,
      malware_scan_status: "succeeded" as const,
      parse_status: "succeeded" as const,
      retrieval_status: "not_started" as const,
      governance_status: "not_started" as const,
      malware_scanner: "clamav",
      malware_signature_version: "1",
      malware_scanned_at: "2026-07-20T00:01:00Z",
      quarantine_status: "not_applicable" as const,
      quarantine_version: 0,
      quarantine_updated_at: null,
      extracted_text_sha256: "b".repeat(64),
      parser_name: "pypdf",
      parser_version: "6.0",
      metadata_json: { parser: { page_count: 3 } },
      error_code: null,
      error_message: null,
      replayable_stages: [],
    },
  ];
  vi.mocked(loadDataFactory).mockResolvedValue(snapshot);
  vi.mocked(loadSourceAssets).mockResolvedValue({ items: [asset], total: 1, limit: 50, offset: 0 });
  vi.mocked(loadSourceAsset).mockResolvedValue({ ...asset, versions });
  vi.mocked(loadSourceVersionPreview).mockResolvedValue({
    source_version_id: "version-1",
    text: "[[page:1]] EGFR evidence",
    truncated: false,
    returned_chars: 24,
    extracted_text_sha256: "b".repeat(64),
  });
  vi.mocked(replaySourceVersion).mockResolvedValue({
    workflow_id: "source-version-reprocess-version-2",
    source_version_id: "version-2",
    from_stage: "parse",
    status: "accepted",
  });

  renderWithQueryClient(<DataFactoryView user={user} />);

  await verifyDialogKeyboard(await screen.findByRole("button", { name: "查看 egfr.pdf 版本" }), "egfr.pdf");
  expect(await screen.findByRole("dialog", { name: "egfr.pdf" })).toBeInTheDocument();
  expect(screen.getByText("Parser rejected the document")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "查看解析文本" })).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "查看解析文本" }));
  expect(await screen.findByText("[[page:1]] EGFR evidence")).toBeInTheDocument();
  expect(loadSourceVersionPreview).toHaveBeenCalledWith("version-1", expect.any(AbortSignal));
  await verifyDialogKeyboard(screen.getByRole("button", { name: "选择恢复阶段" }), /^重放源版本 /);
  expect(screen.getByLabelText("恢复起点")).toHaveValue("parse");
  expect(screen.getByRole("button", { name: "确认重放" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("重放原因"), {
    target: { value: "Security signatures were updated" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认重放" }));
  await waitFor(() =>
    expect(replaySourceVersion).toHaveBeenCalledWith(
      "version-2",
      expect.stringMatching(/^source-version-replay:/),
      "failed",
      "parse_failed",
      "parse",
      "Security signatures were updated",
    ),
  );
  expect(await screen.findByText("版本重放已提交")).toBeInTheDocument();
});

it("repairs migrated source governance without changing the governed root binding", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  const scan = await screen.findByRole("button", { name: "立即扫描 Legacy literature" });
  expect(scan).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "编辑 Legacy literature" }));
  expect(screen.getByLabelText("服务端只读目录")).toBeDisabled();
  expect(screen.getByLabelText("目标数据集")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("数据负责人"), { target: { value: "Data Governance" } });
  fireEvent.change(screen.getByLabelText("授权范围编号（每行一个）"), {
    target: { value: "contract:restored-2026" },
  });
  fireEvent.change(screen.getByLabelText("授权结束时间（留空表示长期有效）"), {
    target: { value: "2027-12-31T00:00" },
  });
  fireEvent.click(screen.getByRole("button", { name: "保存" }));

  await waitFor(() => expect(updateDataSource).toHaveBeenCalledOnce());
  expect(updateDataSource).toHaveBeenCalledWith(
    "source-1",
    expect.objectContaining({
      owner: "Data Governance",
      authorization_scopes: ["contract:restored-2026"],
      authorization_valid_until: expect.any(String),
    }),
  );
  expect(vi.mocked(updateDataSource).mock.calls[0]?.[1]).toEqual(
    expect.objectContaining({
      authorization_valid_until: new Date(2027, 11, 31, 0, 0).toISOString(),
    }),
  );
  expect(vi.mocked(updateDataSource).mock.calls[0]?.[1]).not.toHaveProperty("root_uri");
  expect(vi.mocked(updateDataSource).mock.calls[0]?.[1]).not.toHaveProperty("dataset_key");
});

it("registers an HTTP manifest source with a credential reference but never a credential value", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  await screen.findByText("Legacy literature");
  fireEvent.click(screen.getByRole("button", { name: "接入自动数据源" }));
  fireEvent.change(screen.getByLabelText("数据源类型"), { target: { value: "http_manifest" } });
  fireEvent.change(screen.getByLabelText("数据源名称"), { target: { value: "Licensed supplier API" } });
  fireEvent.change(screen.getByLabelText("Manifest API 地址"), {
    target: { value: "https://supplier.example/v1/manifest" },
  });
  fireEvent.change(screen.getByLabelText("凭据引用"), { target: { value: "env://SUPPLIER_API_TOKEN" } });
  fireEvent.change(screen.getByLabelText("数据负责人"), { target: { value: "Scientific Data Operations" } });
  fireEvent.change(screen.getByLabelText("授权范围编号（每行一个）"), {
    target: { value: "contract:supplier-2026" },
  });
  fireEvent.click(screen.getByRole("button", { name: "注册" }));

  await waitFor(() => expect(createDataSource).toHaveBeenCalledOnce());
  expect(createDataSource).toHaveBeenCalledWith(
    expect.objectContaining({
      source_type: "http_manifest",
      root_uri: "https://supplier.example/v1/manifest",
      credential_ref: "env://SUPPLIER_API_TOKEN",
      stable_seconds: 0,
    }),
  );
  expect(JSON.stringify(vi.mocked(createDataSource).mock.calls[0]?.[0])).not.toContain("registration-only-token");
});

it("registers a governed PubMed query without asking for credentials", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  await screen.findByText("Legacy literature");
  fireEvent.click(screen.getByRole("button", { name: "接入自动数据源" }));
  fireEvent.change(screen.getByLabelText("数据源类型"), { target: { value: "pubmed" } });
  fireEvent.change(screen.getByLabelText("数据源名称"), { target: { value: "EGFR PubMed" } });
  fireEvent.change(screen.getByLabelText("PubMed 检索主题"), {
    target: { value: "EGFR AND lung cancer" },
  });
  fireEvent.change(screen.getByLabelText("单次最多抓取记录"), { target: { value: "150" } });
  fireEvent.change(screen.getByLabelText("每页请求数量"), { target: { value: "100" } });
  fireEvent.click(screen.getByLabelText("同时入库摘要"));
  fireEvent.change(screen.getByLabelText("数据负责人"), { target: { value: "Scientific Data Operations" } });

  expect(screen.queryByLabelText("凭据引用")).not.toBeInTheDocument();
  expect(screen.getByLabelText("数据分级")).toHaveValue("public");
  expect(screen.getByLabelText("授权范围编号（每行一个）")).toHaveValue(
    "public:ncbi-pubmed-metadata\npublic:ncbi-pubmed-abstracts",
  );
  expect(screen.getByLabelText("PubMed API 地址")).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "注册" }));

  await waitFor(() => expect(createDataSource).toHaveBeenCalledOnce());
  expect(createDataSource).toHaveBeenCalledWith(
    expect.objectContaining({
      source_type: "pubmed",
      root_uri: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
      data_classification: "public",
      authorization_scopes: ["public:ncbi-pubmed-metadata", "public:ncbi-pubmed-abstracts"],
      routing_rules: [
        {
          query_term: "EGFR AND lung cancer",
          max_records: 150,
          page_size: 100,
          include_abstract: true,
        },
      ],
      stable_seconds: 0,
    }),
  );
  expect(vi.mocked(createDataSource).mock.calls[0]?.[0]).not.toHaveProperty("credential_ref");
});

it("registers a governed ClinicalTrials.gov query without asking for credentials", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  await screen.findByText("Legacy literature");
  fireEvent.click(screen.getByRole("button", { name: "接入自动数据源" }));
  fireEvent.change(screen.getByLabelText("数据源类型"), { target: { value: "clinicaltrials_gov" } });
  fireEvent.change(screen.getByLabelText("数据源名称"), { target: { value: "EGFR ClinicalTrials.gov" } });
  fireEvent.change(screen.getByLabelText("ClinicalTrials.gov 检索主题"), {
    target: { value: "AREA[ConditionSearch]lung cancer AND AREA[InterventionSearch]EGFR" },
  });
  fireEvent.change(screen.getByLabelText("单次最多抓取记录"), { target: { value: "200" } });
  fireEvent.change(screen.getByLabelText("每页请求数量"), { target: { value: "100" } });
  fireEvent.change(screen.getByLabelText("结果排序"), { target: { value: "StudyFirstPostDate:desc" } });
  fireEvent.change(screen.getByLabelText("历史起始日期"), { target: { value: "2026-07-01" } });
  fireEvent.change(screen.getByLabelText("数据负责人"), { target: { value: "Clinical Intelligence" } });

  expect(screen.queryByLabelText("凭据引用")).not.toBeInTheDocument();
  expect(screen.getByLabelText("数据分级")).toHaveValue("public");
  expect(screen.getByLabelText("授权范围编号（每行一个）")).toHaveValue("public:clinicaltrials-gov");
  expect(screen.getByLabelText("ClinicalTrials.gov API 地址")).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "注册" }));

  await waitFor(() => expect(createDataSource).toHaveBeenCalledOnce());
  expect(createDataSource).toHaveBeenCalledWith(
    expect.objectContaining({
      source_type: "clinicaltrials_gov",
      root_uri: "https://clinicaltrials.gov/api/v2/studies",
      data_classification: "public",
      authorization_scopes: ["public:clinicaltrials-gov"],
      routing_rules: [
        {
          query_term: "AREA[ConditionSearch]lung cancer AND AREA[InterventionSearch]EGFR",
          max_records: 200,
          page_size: 100,
          sort: "StudyFirstPostDate:desc",
          sync_mode: "continuous",
          start_date: "2026-07-01",
          window_days: 31,
          overlap_days: 2,
          reconcile_interval_days: 30,
        },
      ],
      stable_seconds: 0,
    }),
  );
  expect(vi.mocked(createDataSource).mock.calls[0]?.[0]).not.toHaveProperty("credential_ref");
});

it("registers an S3 snapshot source through the existing data factory", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  await screen.findByText("Legacy literature");
  fireEvent.click(screen.getByRole("button", { name: "接入自动数据源" }));
  fireEvent.change(screen.getByLabelText("数据源类型"), { target: { value: "s3_snapshot" } });
  fireEvent.change(screen.getByLabelText("数据源名称"), { target: { value: "Supplier data lake" } });
  fireEvent.change(screen.getByLabelText("S3 Bucket / Prefix"), {
    target: { value: "s3://licensed-supplier/research/" },
  });
  fireEvent.change(screen.getByLabelText("凭据引用"), {
    target: { value: "env://SUPPLIER_S3_CREDENTIALS_JSON" },
  });
  fireEvent.change(screen.getByLabelText("数据负责人"), { target: { value: "Scientific Data Operations" } });
  fireEvent.change(screen.getByLabelText("授权范围编号（每行一个）"), {
    target: { value: "contract:supplier-s3-2026" },
  });
  fireEvent.click(screen.getByRole("button", { name: "注册" }));

  await waitFor(() => expect(createDataSource).toHaveBeenCalledOnce());
  expect(createDataSource).toHaveBeenCalledWith(
    expect.objectContaining({
      source_type: "s3_snapshot",
      root_uri: "s3://licensed-supplier/research/",
      credential_ref: "env://SUPPLIER_S3_CREDENTIALS_JSON",
      stable_seconds: 0,
    }),
  );
});

it("registers an SFTP snapshot source through the existing data factory", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  await screen.findByText("Legacy literature");
  fireEvent.click(screen.getByRole("button", { name: "接入自动数据源" }));
  fireEvent.change(screen.getByLabelText("数据源类型"), { target: { value: "sftp_snapshot" } });
  fireEvent.change(screen.getByLabelText("数据源名称"), { target: { value: "Supplier SFTP delivery" } });
  fireEvent.change(screen.getByLabelText("SFTP 目录地址"), {
    target: { value: "sftp://supplier.example:22/delivery/" },
  });
  fireEvent.change(screen.getByLabelText("凭据引用"), {
    target: { value: "env://SUPPLIER_SFTP_CREDENTIALS_JSON" },
  });
  fireEvent.change(screen.getByLabelText("数据负责人"), { target: { value: "Scientific Data Operations" } });
  fireEvent.change(screen.getByLabelText("授权范围编号（每行一个）"), {
    target: { value: "contract:supplier-sftp-2026" },
  });
  fireEvent.click(screen.getByRole("button", { name: "注册" }));

  await waitFor(() => expect(createDataSource).toHaveBeenCalledOnce());
  expect(createDataSource).toHaveBeenCalledWith(
    expect.objectContaining({
      source_type: "sftp_snapshot",
      root_uri: "sftp://supplier.example:22/delivery/",
      credential_ref: "env://SUPPLIER_SFTP_CREDENTIALS_JSON",
      stable_seconds: 0,
    }),
  );
});

it("registers an encrypted SMB snapshot source without accepting a password value", async () => {
  renderWithQueryClient(<DataFactoryView user={user} />);

  await screen.findByText("Legacy literature");
  fireEvent.click(screen.getByRole("button", { name: "接入自动数据源" }));
  fireEvent.change(screen.getByLabelText("数据源类型"), { target: { value: "smb_snapshot" } });
  fireEvent.change(screen.getByLabelText("数据源名称"), { target: { value: "Enterprise research share" } });
  fireEvent.change(screen.getByLabelText("SMB 共享目录地址"), {
    target: { value: "smb://fileserver.example:445/research/delivery/" },
  });
  fireEvent.change(screen.getByLabelText("凭据引用"), {
    target: { value: "env://ENTERPRISE_SMB_CREDENTIALS_JSON" },
  });
  fireEvent.change(screen.getByLabelText("数据负责人"), { target: { value: "Scientific Data Operations" } });
  fireEvent.change(screen.getByLabelText("授权范围编号（每行一个）"), {
    target: { value: "contract:enterprise-smb-2026" },
  });
  fireEvent.click(screen.getByRole("button", { name: "注册" }));

  await waitFor(() => expect(createDataSource).toHaveBeenCalledOnce());
  expect(createDataSource).toHaveBeenCalledWith(
    expect.objectContaining({
      source_type: "smb_snapshot",
      root_uri: "smb://fileserver.example:445/research/delivery/",
      credential_ref: "env://ENTERPRISE_SMB_CREDENTIALS_JSON",
      stable_seconds: 0,
    }),
  );
  expect(JSON.stringify(vi.mocked(createDataSource).mock.calls[0]?.[0])).not.toContain("password");
});
