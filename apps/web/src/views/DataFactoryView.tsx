import { useQuery } from "@tanstack/react-query";
import {
  BrainCircuit,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleStop,
  CloudDownload,
  Eye,
  FileCheck2,
  FileText,
  FolderCog,
  FolderSync,
  type LucideIcon,
  Pause,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import {
  EmptyState,
  ErrorState,
  formatDate,
  humanBytes,
  Spinner,
  StatusBadge,
  statusLabel,
} from "../components/common";
import type {
  DataSource,
  DataSourceDataset,
  IngestionFinding,
  IngestionRun,
  QuarantineAction,
  QuarantineCase,
  SourceVersion,
  SourceVersionReplayStage,
} from "../lib/contracts/dataFactory";
import {
  cancelIngestionRun,
  createDataSource,
  dataFactoryKeys,
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
  triggerDataSourceScan,
  updateDataSource,
  updateDataSourceState,
} from "../lib/contracts/dataFactory";
import type { DataSourceCreate } from "../lib/generated/models/DataSourceCreate";
import type { User } from "../lib/types";
import { useModalFocus } from "../lib/useModalFocus";

const RUNS_PER_PAGE = 25;
const ASSETS_PER_PAGE = 50;
type ReplayableRunState = "failed" | "partial" | "canceled";
const VERSION_REPLAY_STAGE_LABELS: Record<SourceVersionReplayStage, string> = {
  malware_scan: "安全扫描",
  parse: "文档解析",
  governance: "AI 治理",
  retrieval: "检索投影",
};
const ACTIVE_QUARANTINE_STATUSES = new Set(["pending_review", "held", "rescan_requested"]);
const QUARANTINE_ACTION_LABELS: Record<QuarantineAction, string> = {
  hold: "留置待审",
  reject: "永久拒绝",
  rescan: "重新安全扫描",
};
const QUARANTINE_DECISION_LABELS: Record<string, string> = {
  scan_detected: "扫描发现威胁",
  hold: "留置待审",
  reject: "永久拒绝",
  rescan: "申请重新扫描",
  scan_clean: "复扫结果清洁",
  rescan_failed: "复扫启动失败",
};

const PUBLIC_RESEARCH_SOURCES = {
  pubmed: {
    rootUri: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
    authorizationScope: "public:ncbi-pubmed-metadata",
  },
  clinicaltrials_gov: {
    rootUri: "https://clinicaltrials.gov/api/v2/studies",
    authorizationScope: "public:clinicaltrials-gov",
  },
} as const;

type PublicResearchSourceType = keyof typeof PUBLIC_RESEARCH_SOURCES;
type ClinicalTrialsSort =
  | "LastUpdatePostDate:asc"
  | "LastUpdatePostDate:desc"
  | "StudyFirstPostDate:asc"
  | "StudyFirstPostDate:desc";

function clinicalTrialsSort(value: unknown): ClinicalTrialsSort {
  if (
    value === "LastUpdatePostDate:asc" ||
    value === "LastUpdatePostDate:desc" ||
    value === "StudyFirstPostDate:asc" ||
    value === "StudyFirstPostDate:desc"
  ) {
    return value;
  }
  return "LastUpdatePostDate:desc";
}

function isPublicResearchSource(sourceType: DataSource["source_type"]): sourceType is PublicResearchSourceType {
  return sourceType in PUBLIC_RESEARCH_SOURCES;
}

function sourceRequiresCredential(sourceType: DataSource["source_type"]): boolean {
  return ["http_manifest", "s3_snapshot", "sftp_snapshot", "smb_snapshot"].includes(sourceType);
}

function sourceRootLabel(sourceType: DataSource["source_type"]): string {
  if (sourceType === "folder") return "服务端只读目录";
  if (sourceType === "http_manifest") return "Manifest API 地址";
  if (sourceType === "pubmed") return "PubMed API 地址";
  if (sourceType === "clinicaltrials_gov") return "ClinicalTrials.gov API 地址";
  if (sourceType === "s3_snapshot") return "S3 Bucket / Prefix";
  if (sourceType === "sftp_snapshot") return "SFTP 目录地址";
  return "SMB 共享目录地址";
}

const DATA_FACTORY_STATUS_LABELS: Record<string, string> = {
  "projection ready": "检索投影正常",
  "projection unavailable": "检索投影不可用",
  "scheduler active": "调度已启用",
  "scheduler disabled": "调度未启用",
};

function dataFactoryStatusLabel(value: string): string {
  return DATA_FACTORY_STATUS_LABELS[value] ?? statusLabel(value);
}

const SOURCE_READINESS_GUIDANCE: Record<string, string> = {
  owner: "请指定可追责的数据负责人",
  authorization_scopes: "请登记至少一个有效的来源授权范围",
  authorization_window: "请检查来源授权的生效与结束时间",
  authorization_not_yet_valid: "来源授权尚未生效，请检查生效时间",
  authorization_expired: "来源授权已过期，请更新授权",
  authorization_expiring: "来源授权即将到期，请及时续期",
  data_classification: "请选择有效的数据分级",
  connector: "当前数据源类型没有可用连接器",
  connector_configuration: "连接器配置未通过，请检查来源地址与抓取参数",
  credential_ref: "请绑定已托管的凭据引用",
  dataset: "目标数据集未登记或已停用",
  license_policy: "目标数据集授权策略无效或当前不可交付",
  delivery_channels: "数据集授权未同时覆盖 Web 与 MCP",
};

function sourceReadinessGuidance(check: { code: string; message: string }): string {
  if (check.code === "freshness") {
    return check.message.includes("first scan") ? "尚未完成首次扫描" : "数据源已超过更新时效目标";
  }
  return SOURCE_READINESS_GUIDANCE[check.code] ?? "数据源治理检查未通过，请检查配置";
}

function toLocalDateTimeInput(value?: string | null): string {
  const date = value ? new Date(value) : new Date();
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function DataFactoryView({ user }: { user: User }) {
  const [selectedRun, setSelectedRun] = useState<IngestionRun | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editingSource, setEditingSource] = useState<DataSource | null>(null);
  const [replayRun, setReplayRun] = useState<IngestionRun | null>(null);
  const [cancelRun, setCancelRun] = useState<IngestionRun | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedQuarantineVersionId, setSelectedQuarantineVersionId] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState("");
  const [runPage, setRunPage] = useState(0);
  const [assetPage, setAssetPage] = useState(0);
  const snapshot = useQuery({
    queryKey: dataFactoryKeys.all,
    queryFn: ({ signal }) => loadDataFactory(signal),
  });
  const findingsQuery = useQuery({
    queryKey: dataFactoryKeys.findings(selectedRun?.id ?? "none"),
    queryFn: ({ signal }) => loadIngestionFindings(selectedRun?.id ?? "", signal),
    enabled: Boolean(selectedRun),
  });
  const assetsQuery = useQuery({
    queryKey: ["data-factory", "assets", assetPage],
    queryFn: ({ signal }) => loadSourceAssets(assetPage * ASSETS_PER_PAGE, ASSETS_PER_PAGE, signal),
  });
  const searchStatusQuery = useQuery({
    queryKey: dataFactoryKeys.searchStatus,
    queryFn: ({ signal }) => loadSearchProjectionStatus(signal),
  });
  const sources = snapshot.data?.sources;
  const capabilities = snapshot.data?.capabilities;
  const datasets = snapshot.data?.datasets ?? [];
  const readiness = snapshot.data?.readiness ?? [];
  const searchStatus = searchStatusQuery.data;
  const runs = snapshot.data?.runs ?? [];
  const quarantineCases = snapshot.data?.quarantineCases ?? [];
  const activeQuarantineCases = quarantineCases.filter((item) =>
    ACTIVE_QUARANTINE_STATUSES.has(item.quarantine_status),
  );
  const assets = assetsQuery.data?.items ?? [];
  const assetTotal = assetsQuery.data?.total ?? 0;
  const assetPageCount = Math.max(1, Math.ceil(assetTotal / ASSETS_PER_PAGE));
  const runPageCount = Math.max(1, Math.ceil(runs.length / RUNS_PER_PAGE));
  const currentRunPage = Math.min(runPage, runPageCount - 1);
  const visibleRuns = runs.slice(currentRunPage * RUNS_PER_PAGE, (currentRunPage + 1) * RUNS_PER_PAGE);
  const queryError = snapshot.error instanceof Error ? snapshot.error.message : "";
  const error = actionError || queryError;
  const readySources = readiness.filter((item) => item.operational_status === "ready").length;
  const activeSources = sources?.filter((source) => source.state === "active").length ?? 0;
  const latestRun = runs[0];

  async function load() {
    setActionError("");
    void searchStatusQuery.refetch();
    await Promise.all([snapshot.refetch(), assetsQuery.refetch()]);
  }

  async function action(source: DataSource, kind: "scan" | "pause" | "resume") {
    setBusy(`${source.id}:${kind}`);
    setActionError("");
    try {
      if (kind === "scan") await triggerDataSourceScan(source.id);
      else await updateDataSourceState(source.id, kind === "pause" ? "paused" : "active");
      await load();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "操作失败");
    } finally {
      setBusy("");
    }
  }

  function showFindings(run: IngestionRun) {
    setSelectedRun(run);
  }

  async function replay(operationKey: string, reason: string) {
    if (!replayRun) return;
    if (!["failed", "partial", "canceled"].includes(replayRun.state)) {
      setActionError("当前运行状态不允许重放，请刷新后重试");
      return;
    }
    setBusy(`run:${replayRun.id}:replay`);
    setActionError("");
    try {
      await replayIngestionRun(replayRun.id, operationKey, replayRun.state as ReplayableRunState, reason);
      setReplayRun(null);
      await load();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "入库运行重放失败");
    } finally {
      setBusy("");
    }
  }

  async function cancel(operationKey: string, reason: string) {
    if (!cancelRun) return;
    if (!cancelRun.cancelable || cancelRun.effective_state !== "running") {
      setActionError("当前运行已不能取消，请刷新后重试");
      return;
    }
    setBusy(`run:${cancelRun.id}:cancel`);
    setActionError("");
    try {
      await cancelIngestionRun(cancelRun.id, operationKey, reason);
      setCancelRun(null);
      setSelectedRun(null);
      await load();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "入库运行取消失败");
    } finally {
      setBusy("");
    }
  }

  if (!sources && snapshot.isPending) return <Spinner label="正在连接数据工厂" />;
  if (error && !sources) return <ErrorState message={error} retry={load} />;
  return (
    <section className="factory-layout">
      <div className="factory-main">
        {capabilities ? (
          <>
            <section className="factory-status-strip" aria-label="自动入库运行状态">
              <div>
                <span>自动数据源</span>
                <strong>{activeSources}</strong>
                <small>已启用 / {sources?.length ?? 0} 已注册</small>
              </div>
              <div>
                <span>就绪数据源</span>
                <strong>{readySources}</strong>
                <small>{readiness.length - readySources} 个待处理</small>
              </div>
              <div>
                <span>第三方 LLM API</span>
                <strong>
                  {capabilities.ai_governance_enabled && capabilities.ai_model_configured
                    ? "远程 API 已启用"
                    : "待配置"}
                </strong>
                <small>{capabilities.ai_model ? `远程 API · ${capabilities.ai_model}` : "未绑定第三方 API"}</small>
              </div>
              <div>
                <span>最近运行</span>
                <strong>{latestRun ? dataFactoryStatusLabel(latestRun.effective_state) : "暂无"}</strong>
                <small>{latestRun ? formatDate(latestRun.created_at, true) : "等待数据源"}</small>
              </div>
            </section>

            <section className="pipeline-panel" aria-labelledby="pipeline-title">
              <header>
                <div>
                  <h2 id="pipeline-title">自动入库治理链路</h2>
                  <p>文件发现后自动执行版本快照、解析、AI 结构化治理、审核分流和检索发布</p>
                </div>
                <StatusBadge
                  value={capabilities.automatic_scheduling_enabled ? "scheduler active" : "scheduler disabled"}
                  label={dataFactoryStatusLabel(
                    capabilities.automatic_scheduling_enabled ? "scheduler active" : "scheduler disabled",
                  )}
                />
              </header>
              <div className="pipeline-stages">
                <PipelineStage
                  icon={FolderCog}
                  title="目录发现"
                  detail={`${capabilities.allowed_folder_roots.length} 个允许根目录`}
                  ready={capabilities.automatic_scheduling_enabled}
                />
                <PipelineStage
                  icon={FileCheck2}
                  title="安全解析"
                  detail={capabilities.isolated_parser_enabled ? "隔离解析服务" : "进程内解析"}
                  ready={capabilities.isolated_parser_enabled}
                />
                <PipelineStage
                  icon={BrainCircuit}
                  title="远程 API 治理"
                  detail={capabilities.ai_model ? `第三方 API · ${capabilities.ai_model}` : "第三方 API 未配置"}
                  ready={capabilities.ai_governance_enabled && capabilities.ai_model_configured}
                />
                <PipelineStage icon={ShieldCheck} title="质量审核" detail="低置信度进入审核队列" ready />
                <PipelineStage icon={ScanSearch} title="发布检索" detail="Web 与 MCP 同源引用" ready />
              </div>
            </section>

            {searchStatus ? (
              <section className="pipeline-panel" aria-labelledby="projection-status-title">
                <header>
                  <div>
                    <h2 id="projection-status-title">检索投影运行状态</h2>
                    <p>OpenSearch 集群、别名和投递队列来自实时服务状态，不由浏览器推断</p>
                  </div>
                  <StatusBadge
                    value={searchStatus.available ? "projection ready" : "projection unavailable"}
                    label={dataFactoryStatusLabel(
                      searchStatus.available ? "projection ready" : "projection unavailable",
                    )}
                  />
                </header>
                <dl className="enterprise-tenant-details">
                  <div>
                    <dt>集群</dt>
                    <dd>{searchStatus.cluster_name ?? "未连接"}</dd>
                  </div>
                  <div>
                    <dt>集群状态</dt>
                    <dd>
                      {searchStatus.cluster_status ??
                        (searchStatus.error ? "连接失败，请检查检索服务配置与网络" : "未披露")}
                    </dd>
                  </div>
                  <div>
                    <dt>版本</dt>
                    <dd>{searchStatus.version ?? "未披露"}</dd>
                  </div>
                  <div>
                    <dt>索引别名</dt>
                    <dd>{Object.keys(searchStatus.aliases).length}</dd>
                  </div>
                  <div>
                    <dt>待投递</dt>
                    <dd>{searchStatus.deliveries.pending ?? 0}</dd>
                  </div>
                  <div>
                    <dt>失败投递</dt>
                    <dd>{searchStatus.deliveries.failed ?? 0}</dd>
                  </div>
                </dl>
              </section>
            ) : null}

            {!capabilities.ai_governance_enabled || !capabilities.ai_model_configured ? (
              <div className="factory-warning" role="status">
                <BrainCircuit size={17} />
                <span>
                  <strong>第三方 LLM API 尚未启用</strong>
                  当前文件可自动发现并解析，但结构化事实抽取会跳过；生产环境需绑定获批准的远程 HTTPS API 后启用。
                </span>
              </div>
            ) : null}

            <section className="quarantine-panel" aria-labelledby="quarantine-title">
              <header>
                <div>
                  <h2 id="quarantine-title">恶意文件隔离</h2>
                  <p>安全扫描命中的源版本不会进入解析、AI 治理或检索发布，必须经过受审计的人工处置。</p>
                </div>
                <span
                  className="quarantine-count"
                  role="status"
                  aria-label={`${activeQuarantineCases.length} 个待处置案件`}
                >
                  <ShieldAlert size={16} />
                  {activeQuarantineCases.length} 待处置
                </span>
              </header>
              {quarantineCases.length ? (
                <div className="table-frame quarantine-table">
                  <table>
                    <thead>
                      <tr>
                        <th>隔离文件</th>
                        <th>威胁</th>
                        <th>处置状态</th>
                        <th>决策版本</th>
                        <th>最近变更</th>
                        <th aria-label="操作" />
                      </tr>
                    </thead>
                    <tbody>
                      {quarantineCases.map((item) => (
                        <tr key={item.source_version_id}>
                          <td>
                            <span className="quarantine-file">
                              <strong>{item.file_name}</strong>
                              <small className="mono-cell">{item.logical_path}</small>
                            </span>
                          </td>
                          <td className="quarantine-threat">{item.threat_name ?? "未披露签名"}</td>
                          <td>
                            <StatusBadge value={item.quarantine_status} />
                          </td>
                          <td>v{item.quarantine_version}</td>
                          <td>{formatDate(item.updated_at, true)}</td>
                          <td>
                            <button
                              className="secondary-button"
                              type="button"
                              onClick={() => setSelectedQuarantineVersionId(item.source_version_id)}
                            >
                              <ShieldAlert size={15} />
                              {user.role === "admin" && ACTIVE_QUARANTINE_STATUSES.has(item.quarantine_status)
                                ? "处置"
                                : "查看"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="factory-run-empty">
                  <ShieldCheck size={20} />
                  <span>
                    <strong>当前没有隔离案件</strong>
                    <small>扫描命中后，文件会自动阻断并显示在这里。</small>
                  </span>
                </div>
              )}
            </section>
          </>
        ) : null}

        <div className="section-header">
          <div>
            <h2>自动数据源</h2>
            <p>受管目录、对象存储与授权数据接口按计划自动增量同步</p>
          </div>
          <div className="section-actions">
            <button
              className="icon-button"
              type="button"
              onClick={() => void load()}
              title="刷新"
              aria-label="刷新数据工厂"
            >
              <RefreshCw size={17} />
            </button>
            {user.role === "admin" && (sources?.length ?? 0) > 0 ? (
              <button className="primary-button" type="button" onClick={() => setShowCreate(true)}>
                <Plus size={16} />
                接入自动数据源
              </button>
            ) : null}
          </div>
        </div>
        {error ? (
          <div className="inline-error" role="alert">
            {error}
          </div>
        ) : null}
        {sources?.length ? (
          <div className="source-list">
            {sources.map((source) => {
              const sourceReadiness = readiness.find((item) => item.source_id === source.id);
              const scanUnavailableReason =
                capabilities?.durable_workflows_enabled !== true
                  ? "自动扫描工作流尚未启用"
                  : sourceReadiness?.configuration_ready !== true
                    ? "请先完成数据源治理配置"
                    : "立即扫描";
              return (
                <article key={source.id}>
                  <div className="source-icon">
                    {source.source_type === "folder" ? <FolderSync size={21} /> : <CloudDownload size={21} />}
                  </div>
                  <div className="source-core">
                    <div>
                      <h3>{source.name}</h3>
                      <StatusBadge value={sourceReadiness?.operational_status ?? source.state} />
                    </div>
                    <p className="mono-cell">{source.root_uri}</p>
                    <dl>
                      <div>
                        <dt>数据集</dt>
                        <dd>{source.dataset_key}</dd>
                      </div>
                      <div>
                        <dt>扫描周期</dt>
                        <dd>{source.scan_interval_seconds}s</dd>
                      </div>
                      <div>
                        <dt>数据负责人</dt>
                        <dd>{source.owner}</dd>
                      </div>
                      <div>
                        <dt>数据分级</dt>
                        <dd>{source.data_classification}</dd>
                      </div>
                      <div>
                        <dt>授权期限</dt>
                        <dd>
                          {source.authorization_valid_until
                            ? formatDate(source.authorization_valid_until, true)
                            : "长期有效"}
                        </dd>
                      </div>
                      <div>
                        <dt>文件上限</dt>
                        <dd>{humanBytes(source.max_file_bytes)}</dd>
                      </div>
                      <div>
                        <dt>最近成功</dt>
                        <dd>{formatDate(source.last_success_at, true)}</dd>
                      </div>
                    </dl>
                    {sourceReadiness ? (
                      <div className="counter-row">
                        <span>
                          <ShieldCheck size={13} /> {sourceReadiness.connector_id ?? "未识别连接器"}
                        </span>
                        <span>{sourceReadiness.delivery_channels.join(" + ") || "无交付许可"}</span>
                        <span>{sourceReadiness.cursor_present ? "已建立增量游标" : "等待首次游标"}</span>
                      </div>
                    ) : null}
                    {sourceReadiness?.checks
                      .filter((check) => check.status !== "pass")
                      .map((check) => (
                        <p className="source-error" key={`${check.code}:${check.message}`}>
                          {sourceReadinessGuidance(check)}
                        </p>
                      ))}
                    {capabilities?.durable_workflows_enabled === false ? (
                      <p className="source-error">自动扫描工作流尚未启用；完成平台运行配置后才能执行扫描。</p>
                    ) : null}
                    {source.last_error ? <p className="source-error">{source.last_error}</p> : null}
                  </div>
                  {user.role === "admin" ? (
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        type="button"
                        disabled={Boolean(busy) || scanUnavailableReason !== "立即扫描"}
                        onClick={() => void action(source, "scan")}
                        title={scanUnavailableReason}
                        aria-label={`立即扫描 ${source.name}`}
                      >
                        <RefreshCw size={17} />
                      </button>
                      <button
                        className="icon-button"
                        type="button"
                        disabled={Boolean(busy)}
                        onClick={() => setEditingSource(source)}
                        title="编辑治理配置"
                        aria-label={`编辑 ${source.name}`}
                      >
                        <Pencil size={16} />
                      </button>
                      {source.state === "paused" ? (
                        <button
                          className="icon-button"
                          type="button"
                          disabled={Boolean(busy)}
                          onClick={() => void action(source, "resume")}
                          title="恢复"
                          aria-label={`恢复 ${source.name}`}
                        >
                          <Play size={17} />
                        </button>
                      ) : (
                        <button
                          className="icon-button"
                          type="button"
                          disabled={Boolean(busy)}
                          onClick={() => void action(source, "pause")}
                          title="暂停"
                          aria-label={`暂停 ${source.name}`}
                        >
                          <Pause size={17} />
                        </button>
                      )}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <div className="factory-empty-state">
            <FolderSync size={24} />
            <div>
              <strong>尚未接入自动数据源</strong>
              <p>接入固定只读目录或授权数据接口后，调度器会持续发现新增和变更文件。</p>
            </div>
            {user.role === "admin" ? (
              <button className="secondary-button" type="button" onClick={() => setShowCreate(true)}>
                <Plus size={16} />
                接入自动数据源
              </button>
            ) : null}
          </div>
        )}

        <div className="section-header">
          <div>
            <h2>入库运行记录</h2>
            <p>扫描、快照、解析、投影和治理计数</p>
          </div>
        </div>
        {runs.length ? (
          <div className="table-frame">
            <table>
              <thead>
                <tr>
                  <th>工作流</th>
                  <th>状态</th>
                  <th>运行进度</th>
                  <th>阶段</th>
                  <th>心跳</th>
                  <th>完成时间</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {visibleRuns.map((run) => (
                  <tr key={run.id}>
                    <td className="mono-cell">{run.workflow_id}</td>
                    <td>
                      <StatusBadge value={run.effective_state} label={dataFactoryStatusLabel(run.effective_state)} />
                    </td>
                    <td>
                      <div className="ingestion-run-progress">
                        <span>
                          <strong>{run.progress_percent}%</strong>
                          {runVersionProgressLabel(run)}
                        </span>
                        <progress value={run.progress_percent} max={100} aria-label={`${run.workflow_id} 运行进度`} />
                      </div>
                    </td>
                    <td>
                      <RunStageSummary run={run} />
                    </td>
                    <td>{formatDate(run.heartbeat_at, true)}</td>
                    <td>{formatDate(run.completed_at, true)}</td>
                    <td>
                      <div className="row-actions">
                        <button className="text-button" type="button" onClick={() => showFindings(run)}>
                          运行详情
                        </button>
                        {user.role === "admin" && run.cancelable ? (
                          <button
                            className="icon-button"
                            type="button"
                            disabled={Boolean(busy)}
                            onClick={() => {
                              setActionError("");
                              setCancelRun(run);
                            }}
                            title="取消运行"
                            aria-label={`取消 ${run.workflow_id}`}
                          >
                            <CircleStop size={15} />
                          </button>
                        ) : null}
                        {user.role === "admin" && ["failed", "partial", "canceled"].includes(run.state) ? (
                          <button
                            className="icon-button"
                            type="button"
                            disabled={Boolean(busy)}
                            onClick={() => {
                              setActionError("");
                              setReplayRun(run);
                            }}
                            title="重放运行"
                            aria-label={`重放 ${run.workflow_id}`}
                          >
                            <RotateCcw size={15} />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <nav className="factory-run-pagination" aria-label="入库运行记录分页">
              <span>
                第 {currentRunPage + 1} / {runPageCount} 页，共 {runs.length} 条
              </span>
              <div>
                <button
                  className="icon-button"
                  type="button"
                  aria-label="入库运行记录上一页"
                  title="上一页"
                  disabled={currentRunPage === 0}
                  onClick={() => setRunPage((page) => Math.max(0, page - 1))}
                >
                  <ChevronLeft size={17} />
                </button>
                <button
                  className="icon-button"
                  type="button"
                  aria-label="入库运行记录下一页"
                  title="下一页"
                  disabled={currentRunPage >= runPageCount - 1}
                  onClick={() => setRunPage((page) => Math.min(runPageCount - 1, page + 1))}
                >
                  <ChevronRight size={17} />
                </button>
              </div>
            </nav>
          </div>
        ) : (
          <div className="factory-run-empty">
            <Workflow size={20} />
            <span>
              <strong>暂无运行记录</strong>
              <small>接入数据源后，自动扫描和治理结果会显示在这里。</small>
            </span>
          </div>
        )}

        <div className="section-header">
          <div>
            <h2>源对象与版本</h2>
            <p>只读查看来源路径、版本哈希、处理阶段、恶意文件结果和解析文本</p>
          </div>
        </div>
        {assets.length ? (
          <div className="table-frame">
            <table>
              <thead>
                <tr>
                  <th>文件</th>
                  <th>来源路径</th>
                  <th>状态</th>
                  <th>处理方式</th>
                  <th>最近发现</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {assets.map((asset) => (
                  <tr key={asset.id}>
                    <td>{asset.file_name}</td>
                    <td className="mono-cell">{asset.logical_path}</td>
                    <td>
                      <StatusBadge value={asset.state} />
                    </td>
                    <td>{asset.processing_mode === "parse" ? "真实解析" : "仅登记资产"}</td>
                    <td>{formatDate(asset.last_seen_at, true)}</td>
                    <td>
                      <button
                        className="icon-button"
                        type="button"
                        onClick={() => setSelectedAssetId(asset.id)}
                        title="查看版本"
                        aria-label={`查看 ${asset.file_name} 版本`}
                      >
                        <Eye size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <nav className="factory-run-pagination" aria-label="源对象分页">
              <span>
                第 {assetPage + 1} / {assetPageCount} 页，共 {assetTotal} 个对象
              </span>
              <div>
                <button
                  className="icon-button"
                  type="button"
                  aria-label="源对象上一页"
                  title="上一页"
                  disabled={assetPage === 0}
                  onClick={() => setAssetPage((page) => Math.max(0, page - 1))}
                >
                  <ChevronLeft size={17} />
                </button>
                <button
                  className="icon-button"
                  type="button"
                  aria-label="源对象下一页"
                  title="下一页"
                  disabled={assetPage >= assetPageCount - 1}
                  onClick={() => setAssetPage((page) => Math.min(assetPageCount - 1, page + 1))}
                >
                  <ChevronRight size={17} />
                </button>
              </div>
            </nav>
          </div>
        ) : (
          <div className="factory-run-empty">
            <FileText size={20} />
            <span>
              <strong>暂无源对象</strong>
              <small>自动数据源发现文件后，版本和解析状态会显示在这里。</small>
            </span>
          </div>
        )}
      </div>
      {showCreate ? (
        <CreateSource
          datasets={datasets}
          allowedFolderRoots={capabilities?.allowed_folder_roots ?? []}
          durableWorkflowsEnabled={capabilities?.durable_workflows_enabled === true}
          onClose={() => setShowCreate(false)}
          onCreated={async () => {
            setShowCreate(false);
            await load();
          }}
        />
      ) : null}
      {editingSource ? (
        <CreateSource
          datasets={datasets}
          allowedFolderRoots={capabilities?.allowed_folder_roots ?? []}
          durableWorkflowsEnabled={capabilities?.durable_workflows_enabled === true}
          source={editingSource}
          onClose={() => setEditingSource(null)}
          onCreated={async () => {
            setEditingSource(null);
            await load();
          }}
        />
      ) : null}
      {selectedRun ? (
        <FindingsDrawer
          run={selectedRun}
          findings={findingsQuery.data ?? null}
          error={findingsQuery.error instanceof Error ? findingsQuery.error.message : ""}
          retry={() => void findingsQuery.refetch()}
          onClose={() => {
            setSelectedRun(null);
          }}
        />
      ) : null}
      {replayRun ? (
        <ReplayRunDialog
          run={replayRun}
          busy={busy === `run:${replayRun.id}:replay`}
          error={actionError}
          onClose={() => {
            if (!busy) {
              setActionError("");
              setReplayRun(null);
            }
          }}
          onConfirm={replay}
        />
      ) : null}
      {cancelRun ? (
        <CancelRunDialog
          run={cancelRun}
          busy={busy === `run:${cancelRun.id}:cancel`}
          error={actionError}
          onClose={() => {
            if (!busy) {
              setActionError("");
              setCancelRun(null);
            }
          }}
          onConfirm={cancel}
        />
      ) : null}
      {selectedAssetId ? (
        <SourceAssetDrawer
          assetId={selectedAssetId}
          canManage={user.role === "admin"}
          onClose={() => setSelectedAssetId(null)}
        />
      ) : null}
      {selectedQuarantineVersionId ? (
        <QuarantineDecisionDialog
          versionId={selectedQuarantineVersionId}
          canManage={user.role === "admin"}
          onClose={() => setSelectedQuarantineVersionId(null)}
          onDecided={load}
        />
      ) : null}
    </section>
  );
}

function availableQuarantineActions(status: QuarantineCase["quarantine_status"]): QuarantineAction[] {
  if (status === "pending_review") return ["hold", "reject", "rescan"];
  if (status === "held") return ["reject", "rescan"];
  return [];
}

function QuarantineDecisionDialog({
  versionId,
  canManage,
  onClose,
  onDecided,
}: {
  versionId: string;
  canManage: boolean;
  onClose: () => void;
  onDecided: () => Promise<void>;
}) {
  const quarantine = useQuery({
    queryKey: dataFactoryKeys.quarantine(versionId),
    queryFn: ({ signal }) => loadQuarantineCase(versionId, signal),
  });
  const caseData = quarantine.data;
  const actions = caseData ? availableQuarantineActions(caseData.quarantine_status) : [];
  const [action, setAction] = useState<QuarantineAction>("hold");
  const [reason, setReason] = useState("");
  const [operationKey, setOperationKey] = useState(() => `quarantine-decision:${crypto.randomUUID()}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [accepted, setAccepted] = useState("");

  useEffect(() => {
    if (actions.length > 0 && !actions.includes(action)) setAction(actions[0]);
  }, [action, actions]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!caseData || !actions.includes(action) || reason.trim().length < 3 || busy) return;
    setBusy(true);
    setError("");
    setAccepted("");
    try {
      const result = await decideQuarantineCase(versionId, {
        operation_key: operationKey,
        expected_version: caseData.quarantine_version,
        action,
        reason: reason.trim(),
      });
      setAccepted(
        result.action === "rescan"
          ? `复扫工作流已提交：${result.workflow_id ?? "等待运行标识"}`
          : `处置已记录：${QUARANTINE_ACTION_LABELS[result.action]}`,
      );
      setReason("");
      setOperationKey(`quarantine-decision:${crypto.randomUUID()}`);
      await onDecided();
      await quarantine.refetch();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "隔离案件处置失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        className="modal-panel quarantine-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="quarantine-dialog-title"
      >
        <header>
          <div>
            <p className="eyebrow">MALWARE QUARANTINE</p>
            <h2 id="quarantine-dialog-title">隔离案件处置</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            disabled={busy}
            title="关闭隔离案件"
            aria-label="关闭隔离案件"
          >
            <X size={18} />
          </button>
        </header>
        {quarantine.isPending ? <Spinner label="正在读取隔离案件" /> : null}
        {quarantine.error instanceof Error ? (
          <div className="quarantine-dialog-state">
            <ErrorState message={quarantine.error.message} retry={() => void quarantine.refetch()} />
          </div>
        ) : null}
        {caseData ? (
          <form onSubmit={submit}>
            <dl className="quarantine-case-summary">
              <div>
                <dt>文件</dt>
                <dd>{caseData.file_name}</dd>
              </div>
              <div>
                <dt>状态</dt>
                <dd>
                  <StatusBadge value={caseData.quarantine_status} />
                </dd>
              </div>
              <div>
                <dt>来源路径</dt>
                <dd className="mono-cell">{caseData.logical_path}</dd>
              </div>
              <div>
                <dt>威胁签名</dt>
                <dd className="quarantine-threat">{caseData.threat_name ?? "未披露"}</dd>
              </div>
              <div>
                <dt>决策版本</dt>
                <dd>v{caseData.quarantine_version}</dd>
              </div>
              <div>
                <dt>最近变更</dt>
                <dd>{formatDate(caseData.updated_at, true)}</dd>
              </div>
            </dl>

            <div className="quarantine-safety-note" role="note">
              <ShieldAlert size={17} />
              <span>重新扫描只会从恶意文件扫描阶段启动，仍强制经过 ClamAV；不会直接进入解析、AI 治理或检索发布。</span>
            </div>

            <section className="quarantine-history" aria-labelledby="quarantine-history-title">
              <h3 id="quarantine-history-title">不可变处置历史</h3>
              {caseData.decisions?.length ? (
                <ol>
                  {caseData.decisions.map((decision) => (
                    <li key={decision.id}>
                      <span className="quarantine-history-version">v{decision.resulting_version}</span>
                      <span>
                        <strong>{QUARANTINE_DECISION_LABELS[decision.action] ?? decision.action}</strong>
                        <small>
                          {decision.actor_id} · {formatDate(decision.created_at, true)}
                        </small>
                        <p>{decision.reason}</p>
                      </span>
                      <StatusBadge value={decision.resulting_status} />
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="field-help">尚无处置历史，案件数据不完整，请联系平台管理员。</p>
              )}
            </section>

            {canManage && actions.length ? (
              <>
                <label>
                  <span>处置动作</span>
                  <select
                    value={action}
                    onChange={(event) => {
                      setAction(event.target.value as QuarantineAction);
                      setOperationKey(`quarantine-decision:${crypto.randomUUID()}`);
                      setError("");
                    }}
                  >
                    {actions.map((item) => (
                      <option key={item} value={item}>
                        {QUARANTINE_ACTION_LABELS[item]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>处置原因</span>
                  <textarea
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    minLength={3}
                    maxLength={500}
                    required
                  />
                </label>
              </>
            ) : (
              <p className="field-help">
                {canManage ? "当前案件状态没有可执行的人工动作。" : "当前账号仅可查看隔离案件与审计历史。"}
              </p>
            )}
            {accepted ? (
              <div className="inline-success" role="status">
                {accepted}
              </div>
            ) : null}
            {error ? (
              <div className="inline-error" role="alert">
                {error}
              </div>
            ) : null}
            <div className="form-actions">
              <button className="secondary-button" type="button" onClick={onClose} disabled={busy}>
                关闭
              </button>
              {canManage && actions.length ? (
                <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
                  <ShieldAlert size={15} />
                  {busy ? "正在提交" : "提交处置"}
                </button>
              ) : null}
            </div>
          </form>
        ) : null}
      </section>
    </div>
  );
}

function SourceAssetDrawer({
  assetId,
  canManage,
  onClose,
}: {
  assetId: string;
  canManage: boolean;
  onClose: () => void;
}) {
  const [previewVersionId, setPreviewVersionId] = useState<string | null>(null);
  const [replayVersion, setReplayVersion] = useState<{
    id: string;
    versionNumber: number;
    state: SourceVersion["state"];
    errorCode: string | null;
    stages: SourceVersionReplayStage[];
  } | null>(null);
  const [replayBusy, setReplayBusy] = useState(false);
  const [replayError, setReplayError] = useState("");
  const [replayAccepted, setReplayAccepted] = useState("");
  const asset = useQuery({
    queryKey: dataFactoryKeys.asset(assetId),
    queryFn: ({ signal }) => loadSourceAsset(assetId, signal),
  });
  const preview = useQuery({
    queryKey: dataFactoryKeys.preview(previewVersionId ?? "none"),
    queryFn: ({ signal }) => loadSourceVersionPreview(previewVersionId ?? "", signal),
    enabled: Boolean(previewVersionId),
  });
  async function replayFailedVersion(operationKey: string, fromStage: SourceVersionReplayStage, reason: string) {
    if (!replayVersion) return;
    setReplayBusy(true);
    setReplayError("");
    try {
      const accepted = await replaySourceVersion(
        replayVersion.id,
        operationKey,
        replayVersion.state,
        replayVersion.errorCode,
        fromStage,
        reason,
      );
      setReplayAccepted(accepted.workflow_id);
      setReplayVersion(null);
    } catch (caught) {
      setReplayError(caught instanceof Error ? caught.message : "源版本重放失败");
    } finally {
      setReplayBusy(false);
    }
  }

  return (
    <div className="drawer-backdrop">
      <button className="drawer-dismiss" type="button" onClick={onClose} aria-label="关闭源对象详情" />
      <aside className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="source-asset-title">
        <header>
          <div>
            <p className="eyebrow">SOURCE ASSET</p>
            <h2 id="source-asset-title">{asset.data?.file_name ?? "源对象版本"}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭" aria-label="关闭源对象详情">
            <X size={18} />
          </button>
        </header>
        <div className="drawer-content">
          {asset.isPending ? <Spinner label="正在读取源对象版本" /> : null}
          {asset.error instanceof Error ? (
            <ErrorState message={asset.error.message} retry={() => void asset.refetch()} />
          ) : null}
          {asset.data ? (
            <>
              {replayAccepted ? (
                <div className="factory-warning" role="status">
                  <RotateCcw size={17} />
                  <span>
                    <strong>版本重放已提交</strong>
                    工作流 <span className="mono-cell">{replayAccepted}</span> 已按指定恢复点提交处理。
                  </span>
                </div>
              ) : null}
              <dl className="enterprise-tenant-details">
                <div>
                  <dt>逻辑路径</dt>
                  <dd className="mono-cell">{asset.data.logical_path}</dd>
                </div>
                <div>
                  <dt>媒体类型</dt>
                  <dd>{asset.data.media_type ?? asset.data.extension}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>{asset.data.state}</dd>
                </div>
                <div>
                  <dt>处理方式</dt>
                  <dd>{asset.data.processing_mode === "parse" ? "真实解析" : "仅登记资产"}</dd>
                </div>
              </dl>
              <section className="drawer-section">
                <h3>不可变版本</h3>
                <div className="source-version-list">
                  {asset.data.versions.map((version) => {
                    const replayableStages = version.replayable_stages ?? [];
                    return (
                      <article key={version.id}>
                        <header>
                          <strong>版本 {version.version_number}</strong>
                          <StatusBadge value={version.state} />
                        </header>
                        <dl>
                          <div>
                            <dt>SHA-256</dt>
                            <dd className="mono-cell">{version.content_sha256}</dd>
                          </div>
                          <div>
                            <dt>大小</dt>
                            <dd>{humanBytes(version.size_bytes)}</dd>
                          </div>
                          <div>
                            <dt>恶意文件扫描</dt>
                            <dd>{version.malware_scan_status}</dd>
                          </div>
                          <div>
                            <dt>解析 / 投影 / 治理</dt>
                            <dd>
                              {version.parse_status} / {version.retrieval_status} / {version.governance_status}
                            </dd>
                          </div>
                          <div>
                            <dt>解析器</dt>
                            <dd>
                              {version.parser_name
                                ? `${version.parser_name} ${version.parser_version ?? ""}`
                                : "未解析"}
                            </dd>
                          </div>
                        </dl>
                        {version.error_message ? <p className="source-error">{version.error_message}</p> : null}
                        {version.extracted_text_sha256 && version.error_code !== "malware_detected" ? (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => setPreviewVersionId(version.id)}
                          >
                            <Eye size={15} />
                            查看解析文本
                          </button>
                        ) : null}
                        {canManage && replayableStages.length > 0 ? (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => {
                              setReplayError("");
                              setReplayVersion({
                                id: version.id,
                                versionNumber: version.version_number,
                                state: version.state,
                                errorCode: version.error_code,
                                stages: replayableStages,
                              });
                            }}
                          >
                            <RotateCcw size={15} />
                            {replayableStages.length > 1
                              ? "选择恢复阶段"
                              : `从${VERSION_REPLAY_STAGE_LABELS[replayableStages[0]]}阶段重放`}
                          </button>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              </section>
              {previewVersionId ? (
                <section className="drawer-section" aria-labelledby="source-preview-title">
                  <h3 id="source-preview-title">解析文本预览</h3>
                  {preview.isPending ? <Spinner label="正在读取解析文本" /> : null}
                  {preview.error instanceof Error ? (
                    <ErrorState message={preview.error.message} retry={() => void preview.refetch()} />
                  ) : null}
                  {preview.data ? (
                    <>
                      <p className="field-help mono-cell">SHA-256 {preview.data.extracted_text_sha256}</p>
                      <pre className="source-text-preview">{preview.data.text}</pre>
                      {preview.data.truncated ? <p className="field-help">预览已按安全字符上限截断</p> : null}
                    </>
                  ) : null}
                </section>
              ) : null}
            </>
          ) : null}
        </div>
      </aside>
      {replayVersion ? (
        <ReplayVersionDialog
          versionNumber={replayVersion.versionNumber}
          errorCode={replayVersion.errorCode}
          stages={replayVersion.stages}
          busy={replayBusy}
          error={replayError}
          onClose={() => {
            if (!replayBusy) {
              setReplayError("");
              setReplayVersion(null);
            }
          }}
          onConfirm={replayFailedVersion}
        />
      ) : null}
    </div>
  );
}

function ReplayVersionDialog({
  versionNumber,
  errorCode,
  stages,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  versionNumber: number;
  errorCode: string | null;
  stages: SourceVersionReplayStage[];
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (operationKey: string, fromStage: SourceVersionReplayStage, reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [fromStage, setFromStage] = useState<SourceVersionReplayStage>(stages.at(-1) ?? "malware_scan");
  const [operationKey] = useState(() => `source-version-replay:${crypto.randomUUID()}`);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (reason.trim().length < 3 || busy) return;
    await onConfirm(operationKey, fromStage, reason.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="replay-version-title">
        <header>
          <div>
            <p className="eyebrow">VERSION RECOVERY</p>
            <h2 id="replay-version-title">重放源版本 {versionNumber}</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            disabled={busy}
            title="关闭"
            aria-label="关闭"
          >
            <X size={18} />
          </button>
        </header>
        <form onSubmit={submit}>
          <p className="field-help">
            恢复只复用已成功且仍可核验的前序产物，并从所选阶段重置后续状态。当前失败代码：
            <span className="mono-cell">{errorCode ?? "无（阶段状态失败）"}</span>
          </p>
          <label>
            <span>恢复起点</span>
            <select
              value={fromStage}
              onChange={(event) => setFromStage(event.target.value as SourceVersionReplayStage)}
            >
              {stages.map((stage) => (
                <option key={stage} value={stage}>
                  {VERSION_REPLAY_STAGE_LABELS[stage]}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>重放原因</span>
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={3}
              maxLength={500}
              required
            />
          </label>
          {error ? (
            <div className="inline-error" role="alert">
              {error}
            </div>
          ) : null}
          <div className="form-actions">
            <button className="secondary-button" type="button" onClick={onClose} disabled={busy}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
              <RotateCcw size={15} />
              {busy ? "正在提交" : "确认重放"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function ReplayRunDialog({
  run,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  run: IngestionRun;
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (operationKey: string, reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [operationKey] = useState(() => `ingestion-replay:${run.id}:${crypto.randomUUID()}`);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (reason.trim().length < 3 || busy) return;
    await onConfirm(operationKey, reason.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="replay-run-title">
        <header>
          <div>
            <p className="eyebrow">INGESTION RECOVERY</p>
            <h2 id="replay-run-title">重放入库运行</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            disabled={busy}
            title="关闭"
            aria-label="关闭"
          >
            <X size={18} />
          </button>
        </header>
        <form onSubmit={submit}>
          <p className="field-help">
            将按当前数据源治理配置重新扫描；原运行与发现项保持不变，新运行会单独记录并写入审计日志。
          </p>
          <label>
            <span>原工作流</span>
            <input value={run.workflow_id} readOnly className="mono-cell" />
          </label>
          <label>
            <span>重放原因</span>
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={3}
              maxLength={500}
              required
            />
          </label>
          {error ? (
            <div className="inline-error" role="alert">
              {error}
            </div>
          ) : null}
          <div className="form-actions">
            <button className="secondary-button" type="button" onClick={onClose} disabled={busy}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
              <RotateCcw size={15} />
              {busy ? "正在提交" : "确认重放"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function CancelRunDialog({
  run,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  run: IngestionRun;
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (operationKey: string, reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [operationKey] = useState(() => `ingestion-cancel:${run.id}:${crypto.randomUUID()}`);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (reason.trim().length < 3 || busy) return;
    await onConfirm(operationKey, reason.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="cancel-run-title">
        <header>
          <div>
            <p className="eyebrow">CONTROLLED CANCELLATION</p>
            <h2 id="cancel-run-title">取消入库运行</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            disabled={busy}
            title="关闭"
            aria-label="关闭"
          >
            <X size={18} />
          </button>
        </header>
        <form onSubmit={submit}>
          <p className="field-help">
            取消请求只发送到该运行绑定的 Temporal 执行。已完成的不可变快照会保留，后续阶段将在安全检查点停止。
          </p>
          <label>
            <span>运行关联标识</span>
            <input value={run.workflow_id} readOnly className="mono-cell" />
          </label>
          <label>
            <span>取消原因</span>
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={3}
              maxLength={500}
              required
            />
          </label>
          {error ? (
            <div className="inline-error" role="alert">
              {error}
            </div>
          ) : null}
          <div className="form-actions">
            <button className="secondary-button" type="button" onClick={onClose} disabled={busy}>
              返回
            </button>
            <button className="danger-button" type="submit" disabled={busy || reason.trim().length < 3}>
              <CircleStop size={15} />
              {busy ? "正在取消" : "确认取消"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

const RUN_STAGE_LABELS: Record<IngestionRun["stages"][number]["stage"], string> = {
  discovery: "发现",
  snapshot: "快照",
  malware_scan: "安全扫描",
  parse: "解析",
  retrieval: "检索投影",
  governance: "AI 治理",
};

function RunStageSummary({ run }: { run: IngestionRun }) {
  return (
    <div className="ingestion-stage-summary" role="img" aria-label={`${run.workflow_id} 阶段摘要`}>
      {run.stages.map((stage) => (
        <span
          key={stage.stage}
          className={`stage-indicator ${stage.status}`}
          title={`${RUN_STAGE_LABELS[stage.stage]}：${stage.status}`}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

function RunStageGraph({ run }: { run: IngestionRun }) {
  return (
    <section className="ingestion-stage-graph" aria-labelledby="run-stage-title">
      <header>
        <div>
          <h3 id="run-stage-title">逐阶段运行图</h3>
          <p>
            总进度 {run.progress_percent}% · {runVersionProgressLabel(run)}
          </p>
        </div>
        <StatusBadge value={run.effective_state} />
      </header>
      <ol>
        {run.stages.map((stage) => (
          <li key={stage.stage} className={stage.status}>
            <span className="stage-node" aria-hidden="true" />
            <div>
              <strong>{RUN_STAGE_LABELS[stage.stage]}</strong>
              <small>
                {stage.total_items
                  ? `${stage.completed_items} 完成 / ${stage.failed_items} 失败 / ${stage.total_items} 总计`
                  : "本次没有待处理版本"}
              </small>
            </div>
            <StatusBadge value={stage.status} />
          </li>
        ))}
      </ol>
    </section>
  );
}

function runVersionProgressLabel(run: IngestionRun): string {
  if (run.total_versions > 0) {
    return `${run.completed_versions}/${run.total_versions} 个版本完成`;
  }
  const discovered = Math.max(
    0,
    run.counters.discovered ?? 0,
    run.stages.find((stage) => stage.stage === "discovery")?.total_items ?? 0,
  );
  return discovered > 0 ? `已检查 ${discovered} 个对象 · 本次无新增版本` : "本次无新增版本";
}

function PipelineStage({
  icon: Icon,
  title,
  detail,
  ready,
}: {
  icon: LucideIcon;
  title: string;
  detail: string;
  ready: boolean;
}) {
  return (
    <div className={ready ? "ready" : "pending"}>
      <span className="pipeline-icon">
        <Icon size={18} />
      </span>
      <span>
        <strong>{title}</strong>
        <small>{detail}</small>
      </span>
      {ready ? <CheckCircle2 size={15} aria-label="已配置" /> : <span className="pipeline-pending">待配置</span>}
    </div>
  );
}

function CreateSource({
  datasets,
  allowedFolderRoots,
  durableWorkflowsEnabled,
  source,
  onClose,
  onCreated,
}: {
  datasets: DataSourceDataset[];
  allowedFolderRoots: string[];
  durableWorkflowsEnabled: boolean;
  source?: DataSource;
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const eligibleDatasets = datasets.filter((dataset) => dataset.active && dataset.license_current);
  const existingRoutingRule = source?.routing_rules[0] as Record<string, unknown> | undefined;
  const [sourceType, setSourceType] = useState<DataSource["source_type"]>(source?.source_type ?? "folder");
  const [name, setName] = useState(source?.name ?? "");
  const [rootUri, setRootUri] = useState(source?.root_uri ?? allowedFolderRoots[0] ?? "/sources/knowledge");
  const [credentialRef, setCredentialRef] = useState("");
  const [owner, setOwner] = useState(source?.owner ?? "");
  const [authorizationScopes, setAuthorizationScopes] = useState(source?.authorization_scopes.join("\n") ?? "");
  const [authorizationValidFrom, setAuthorizationValidFrom] = useState(
    toLocalDateTimeInput(source?.authorization_valid_from),
  );
  const [authorizationValidUntil, setAuthorizationValidUntil] = useState(
    source?.authorization_valid_until ? toLocalDateTimeInput(source.authorization_valid_until) : "",
  );
  const [classification, setClassification] = useState<"public" | "internal" | "confidential" | "restricted">(
    source?.data_classification ?? "internal",
  );
  const [datasetKey, setDatasetKey] = useState(source?.dataset_key ?? eligibleDatasets[0]?.dataset_key ?? "");
  const [interval, setInterval] = useState(source?.scan_interval_seconds ?? 300);
  const [freshness, setFreshness] = useState(source?.expected_freshness_seconds ?? 86400);
  const [queryTerm, setQueryTerm] = useState(
    typeof existingRoutingRule?.query_term === "string" ? existingRoutingRule.query_term : "",
  );
  const [maxRecords, setMaxRecords] = useState(
    typeof existingRoutingRule?.max_records === "number" ? existingRoutingRule.max_records : 100,
  );
  const [pageSize, setPageSize] = useState(
    typeof existingRoutingRule?.page_size === "number" ? existingRoutingRule.page_size : 100,
  );
  const [includeAbstract, setIncludeAbstract] = useState(existingRoutingRule?.include_abstract === true);
  const [clinicalSort, setClinicalSort] = useState<ClinicalTrialsSort>(clinicalTrialsSort(existingRoutingRule?.sort));
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const dialogRef = useModalFocus<HTMLElement>(true, onClose);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const validFrom = new Date(authorizationValidFrom);
      const validUntil = authorizationValidUntil ? new Date(authorizationValidUntil) : null;
      if (Number.isNaN(validFrom.getTime())) throw new Error("授权生效时间无效");
      if (validUntil && (Number.isNaN(validUntil.getTime()) || validUntil <= validFrom)) {
        throw new Error("授权结束时间必须晚于生效时间");
      }
      const routingRules: NonNullable<DataSourceCreate["routing_rules"]> = isPublicResearchSource(sourceType)
        ? [
            sourceType === "pubmed"
              ? {
                  query_term: queryTerm.trim(),
                  max_records: maxRecords,
                  page_size: pageSize,
                  include_abstract: includeAbstract,
                }
              : {
                  query_term: queryTerm.trim(),
                  max_records: maxRecords,
                  page_size: pageSize,
                  sort: clinicalSort,
                },
          ]
        : [];
      if (isPublicResearchSource(sourceType) && !queryTerm.trim()) throw new Error("检索主题不能为空");
      const governance = {
        name: name.trim(),
        owner: owner.trim(),
        data_classification: classification,
        authorization_scopes: authorizationScopes
          .split(/\r?\n|,/)
          .map((scope) => scope.trim())
          .filter(Boolean),
        authorization_valid_from: validFrom.toISOString(),
        authorization_valid_until: validUntil?.toISOString() ?? null,
        scan_interval_seconds: interval,
        expected_freshness_seconds: freshness,
      };
      if (source) {
        await updateDataSource(source.id, {
          ...governance,
          ...(isPublicResearchSource(source.source_type) ? { routing_rules: routingRules } : {}),
          ...(sourceRequiresCredential(source.source_type) && credentialRef.trim()
            ? { credential_ref: credentialRef.trim() }
            : {}),
        });
      } else
        await createDataSource({
          ...governance,
          source_type: sourceType,
          root_uri: rootUri.trim(),
          ...(isPublicResearchSource(sourceType) ? { routing_rules: routingRules } : {}),
          ...(sourceRequiresCredential(sourceType) && credentialRef.trim()
            ? { credential_ref: credentialRef.trim() }
            : {}),
          dataset_key: datasetKey,
          include_globs: ["*", "**/*"],
          exclude_globs: [],
          stable_seconds: sourceType === "folder" ? 30 : 0,
          max_file_bytes: 1073741824,
          rate_limit_per_minute: 60,
        });
      await onCreated();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "注册失败");
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel source-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-source-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">DATA SOURCE</p>
            <h2 id="create-source-title">{source ? "编辑数据源治理配置" : "接入自动数据源"}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭" aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={submit}>
          <div className="source-form-section">
            <header>
              <strong>连接配置</strong>
              <small>
                {durableWorkflowsEnabled
                  ? "数据源注册后立即进入自动调度"
                  : "数据源登记后将在工作流服务启用时进入自动调度"}
              </small>
            </header>
            <div className="source-form-grid">
              <label>
                <span>数据源名称</span>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                  maxLength={200}
                  data-modal-autofocus="true"
                />
              </label>
              {!source ? (
                <label>
                  <span>数据源类型</span>
                  <select
                    value={sourceType}
                    onChange={(event) => {
                      const nextType = event.target.value as DataSource["source_type"];
                      setSourceType(nextType);
                      if (isPublicResearchSource(nextType)) {
                        const publicSource = PUBLIC_RESEARCH_SOURCES[nextType];
                        const preferredDatasetKey = nextType === "pubmed" ? "literature" : "clinical_trials";
                        setRootUri(publicSource.rootUri);
                        setClassification("public");
                        setAuthorizationScopes(publicSource.authorizationScope);
                        if (eligibleDatasets.some((dataset) => dataset.dataset_key === preferredDatasetKey)) {
                          setDatasetKey(preferredDatasetKey);
                        }
                        setQueryTerm("");
                        setMaxRecords(100);
                        setPageSize(100);
                      } else {
                        setRootUri(
                          nextType === "folder"
                            ? (allowedFolderRoots[0] ?? "/sources/knowledge")
                            : nextType === "http_manifest"
                              ? "https://supplier.example/v1/manifest"
                              : nextType === "s3_snapshot"
                                ? "s3://licensed-supplier/research/"
                                : nextType === "sftp_snapshot"
                                  ? "sftp://supplier.example:22/delivery/"
                                  : "smb://fileserver.example:445/research/delivery/",
                        );
                      }
                      setCredentialRef("");
                    }}
                  >
                    <option value="folder">服务端固定只读目录</option>
                    <option value="pubmed">PubMed（NCBI，自动增量）</option>
                    <option value="clinicaltrials_gov">ClinicalTrials.gov（自动增量）</option>
                    <option value="http_manifest">HTTP Manifest API</option>
                    <option value="s3_snapshot">S3 只读快照</option>
                    <option value="sftp_snapshot">SFTP 只读快照</option>
                    <option value="smb_snapshot">SMB / NAS 只读快照</option>
                  </select>
                </label>
              ) : null}
              <div className="source-path-field">
                <label htmlFor="source-root-uri">{sourceRootLabel(sourceType)}</label>
                <input
                  id="source-root-uri"
                  value={rootUri}
                  onChange={(event) => setRootUri(event.target.value)}
                  required
                  disabled={Boolean(source) || isPublicResearchSource(sourceType)}
                  list={sourceType === "folder" ? "allowed-folder-roots" : undefined}
                />
                {sourceType === "folder" && allowedFolderRoots.length ? (
                  <datalist id="allowed-folder-roots">
                    {allowedFolderRoots.map((root) => (
                      <option key={root} value={root} />
                    ))}
                  </datalist>
                ) : null}
                {sourceType === "folder" ? (
                  <small className="field-help">
                    允许根目录：{allowedFolderRoots.join("、") || "部署环境尚未配置"}
                  </small>
                ) : null}
              </div>
              {isPublicResearchSource(sourceType) ? (
                <>
                  <label className="source-path-field">
                    <span>{sourceType === "pubmed" ? "PubMed 检索主题" : "ClinicalTrials.gov 检索主题"}</span>
                    <input
                      value={queryTerm}
                      onChange={(event) => setQueryTerm(event.target.value)}
                      required
                      maxLength={sourceType === "pubmed" ? 2000 : 1000}
                      placeholder={sourceType === "pubmed" ? "EGFR AND lung cancer" : "EGFR AND lung cancer"}
                    />
                  </label>
                  <label>
                    <span>单次最多抓取记录</span>
                    <input
                      type="number"
                      min={1}
                      max={1000}
                      value={maxRecords}
                      onChange={(event) => setMaxRecords(Number(event.target.value))}
                      required
                    />
                  </label>
                  <label>
                    <span>每页请求数量</span>
                    <input
                      type="number"
                      min={1}
                      max={sourceType === "pubmed" ? 200 : 1000}
                      value={pageSize}
                      onChange={(event) => setPageSize(Number(event.target.value))}
                      required
                    />
                  </label>
                  {sourceType === "pubmed" ? (
                    <label className="source-checkbox-field">
                      <input
                        type="checkbox"
                        checked={includeAbstract}
                        onChange={(event) => {
                          const checked = event.target.checked;
                          setIncludeAbstract(checked);
                          setAuthorizationScopes((current) => {
                            const abstractScope = "public:ncbi-pubmed-abstracts";
                            const scopes = current
                              .split(/\r?\n|,/)
                              .map((scope) => scope.trim())
                              .filter(Boolean)
                              .filter((scope) => scope !== abstractScope);
                            if (checked) scopes.push(abstractScope);
                            return scopes.join("\n");
                          });
                        }}
                      />
                      <span>同时入库摘要</span>
                    </label>
                  ) : (
                    <label>
                      <span>结果排序</span>
                      <select
                        value={clinicalSort}
                        onChange={(event) => setClinicalSort(event.target.value as ClinicalTrialsSort)}
                      >
                        <option value="LastUpdatePostDate:desc">最近更新优先</option>
                        <option value="LastUpdatePostDate:asc">最早更新优先</option>
                        <option value="StudyFirstPostDate:desc">最近首次发布优先</option>
                        <option value="StudyFirstPostDate:asc">最早首次发布优先</option>
                      </select>
                    </label>
                  )}
                </>
              ) : null}
              {sourceRequiresCredential(sourceType) ? (
                <label>
                  <span>{source ? "新凭据引用" : "凭据引用"}</span>
                  <input
                    value={credentialRef}
                    onChange={(event) => setCredentialRef(event.target.value)}
                    required={!source && sourceType !== "s3_snapshot"}
                    placeholder={
                      sourceType === "http_manifest"
                        ? "env://SUPPLIER_API_TOKEN"
                        : sourceType === "s3_snapshot"
                          ? "env://SUPPLIER_S3_CREDENTIALS_JSON"
                          : sourceType === "sftp_snapshot"
                            ? "env://SUPPLIER_SFTP_CREDENTIALS_JSON"
                            : "env://ENTERPRISE_SMB_CREDENTIALS_JSON"
                    }
                    maxLength={500}
                    autoComplete="off"
                  />
                </label>
              ) : null}
            </div>
          </div>

          <div className="source-form-section">
            <header>
              <strong>数据治理</strong>
              <small>负责人、授权和用途决定数据是否允许发布</small>
            </header>
            <div className="source-form-grid">
              <label>
                <span>数据负责人</span>
                <input value={owner} onChange={(event) => setOwner(event.target.value)} required maxLength={200} />
              </label>
              <label>
                <span>数据分级</span>
                <select
                  value={classification}
                  onChange={(event) => setClassification(event.target.value as typeof classification)}
                >
                  <option value="public">公开</option>
                  <option value="internal">内部</option>
                  <option value="confidential">机密</option>
                  <option value="restricted">受限</option>
                </select>
              </label>
              <label className="source-path-field">
                <span>授权范围编号（每行一个）</span>
                <textarea
                  value={authorizationScopes}
                  onChange={(event) => setAuthorizationScopes(event.target.value)}
                  required
                  maxLength={12000}
                />
              </label>
              <label>
                <span>授权生效时间</span>
                <input
                  type="datetime-local"
                  value={authorizationValidFrom}
                  onChange={(event) => setAuthorizationValidFrom(event.target.value)}
                  required
                />
              </label>
              <label>
                <span>授权结束时间（留空表示长期有效）</span>
                <input
                  type="datetime-local"
                  value={authorizationValidUntil}
                  min={authorizationValidFrom}
                  onChange={(event) => setAuthorizationValidUntil(event.target.value)}
                />
              </label>
              <label>
                <span>目标数据集</span>
                <select
                  value={datasetKey}
                  onChange={(event) => setDatasetKey(event.target.value)}
                  required
                  disabled={Boolean(source)}
                >
                  {source && !eligibleDatasets.some((dataset) => dataset.dataset_key === source.dataset_key) ? (
                    <option value={source.dataset_key}>{source.dataset_key}</option>
                  ) : null}
                  {eligibleDatasets.map((dataset) => (
                    <option key={dataset.dataset_key} value={dataset.dataset_key}>
                      {dataset.display_name} · {dataset.license_id}/{dataset.license_policy_version}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className="source-form-section">
            <header>
              <strong>自动化策略</strong>
              <small>持续增量扫描，不移动或修改源文件</small>
            </header>
            <div className="source-form-grid compact">
              <label>
                <span>扫描周期（秒）</span>
                <input
                  type="number"
                  min={10}
                  max={86400}
                  value={interval}
                  onChange={(event) => setInterval(Number(event.target.value))}
                  required
                />
              </label>
              <label>
                <span>Freshness 目标（秒）</span>
                <input
                  type="number"
                  min={60}
                  max={31536000}
                  value={freshness}
                  onChange={(event) => setFreshness(Number(event.target.value))}
                  required
                />
              </label>
            </div>
          </div>
          {!source && !eligibleDatasets.length ? (
            <p className="form-error" role="alert">
              当前没有已启用且许可有效的数据集
            </p>
          ) : null}
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose}>
              取消
            </button>
            <button
              className="primary-button"
              type="submit"
              disabled={submitting || (!source && !eligibleDatasets.length)}
            >
              {submitting ? "保存中" : source ? "保存" : "注册"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function FindingsDrawer({
  run,
  findings,
  error,
  retry,
  onClose,
}: {
  run: IngestionRun;
  findings: IngestionFinding[] | null;
  error: string;
  retry: () => void;
  onClose: () => void;
}) {
  const failedStages = run.stages
    .filter((stage) => stage.status === "failed")
    .map((stage) => RUN_STAGE_LABELS[stage.stage]);
  const failureMessage = run.error_summary
    ? run.error_summary
    : failedStages.length
      ? `运行在${failedStages.join("、")}阶段失败，未生成发现项。请查看阶段详情，并在确认原因后重放。`
      : null;

  return (
    <div className="drawer-backdrop" role="presentation">
      <aside className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="finding-title">
        <header>
          <div>
            <p className="eyebrow">INGESTION FINDINGS</p>
            <h2 id="finding-title">运行发现项</h2>
            <small className="mono-cell">{run.workflow_id}</small>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭" aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <div className="drawer-content">
          <RunStageGraph run={run} />
          {failureMessage ? (
            <div className="factory-warning" role="status">
              <ScanSearch size={17} />
              <span>
                <strong>运行说明</strong>
                {failureMessage}
              </span>
            </div>
          ) : null}
          {error ? (
            <ErrorState message={error} retry={retry} />
          ) : findings === null ? (
            <Spinner />
          ) : findings.length ? (
            findings.map((finding) => (
              <article className="finding-record" key={finding.id}>
                <div>
                  <StatusBadge value={finding.stage} />
                  <span className="mono-cell">{finding.code}</span>
                </div>
                <strong>{finding.message}</strong>
                <p className="mono-cell">{finding.source_path}</p>
                <small>
                  {formatDate(finding.occurred_at, true)} · {finding.retryable ? "可重试" : "不可重试"}
                </small>
              </article>
            ))
          ) : failureMessage ? null : (
            <EmptyState title="该运行没有发现项" />
          )}
        </div>
      </aside>
    </div>
  );
}
