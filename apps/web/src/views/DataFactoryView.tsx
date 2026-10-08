import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  CircleStop,
  CloudDownload,
  Eye,
  FileText,
  FolderSync,
  Pause,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { useState } from "react";
import { ErrorState, formatDate, humanBytes, Spinner, StatusBadge, statusLabel } from "../components/common";
import type { DataSource, IngestionRun } from "../lib/contracts/dataFactory";
import {
  cancelIngestionRun,
  dataFactoryKeys,
  loadDataFactory,
  loadIngestionFindings,
  loadSearchProjectionStatus,
  loadSourceAssets,
  replayIngestionRun,
  triggerDataSourceScan,
  updateDataSourceState,
} from "../lib/contracts/dataFactory";
import type { User } from "../lib/types";
import { FindingsDrawer } from "./dataFactory/FindingsDrawer";
import { IngestionFlowOverview } from "./dataFactory/IngestionFlowOverview";
import { CancelRunDialog, ReplayRunDialog } from "./dataFactory/IngestionRunDialogs";
import { QuarantineCasesPanel } from "./dataFactory/QuarantineCasesPanel";
import { QuarantineDecisionDialog } from "./dataFactory/QuarantineDecisionDialog";
import { RunStageSummary, runVersionProgressLabel } from "./dataFactory/RunStagePresentation";
import { SearchProjectionPanel } from "./dataFactory/SearchProjectionPanel";
import { SourceAssetDrawer } from "./dataFactory/SourceAssetDrawer";
import { SourceEditorDialog } from "./dataFactory/SourceEditorDialog";
import { SourceSyncStatus } from "./dataFactory/SourceSyncStatus";

const RUNS_PER_PAGE = 25;
const ASSETS_PER_PAGE = 50;
type ReplayableRunState = "failed" | "partial" | "canceled";
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
                <strong>{latestRun ? statusLabel(latestRun.effective_state) : "暂无"}</strong>
                <small>{latestRun ? formatDate(latestRun.created_at, true) : "等待数据源"}</small>
              </div>
            </section>

            <QuarantineCasesPanel
              items={quarantineCases}
              role={user.role}
              stale={snapshot.isError}
              onOpen={setSelectedQuarantineVersionId}
            />
            <SearchProjectionPanel
              data={searchStatus}
              pending={searchStatusQuery.isPending}
              error={searchStatusQuery.error instanceof Error ? searchStatusQuery.error : null}
              onRetry={() => void searchStatusQuery.refetch()}
            />
            <IngestionFlowOverview capabilities={capabilities} stale={snapshot.isError} />
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
                    <SourceSyncStatus readiness={sourceReadiness} />
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
                      <StatusBadge value={run.effective_state} label={statusLabel(run.effective_state)} />
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
        <SourceEditorDialog
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
        <SourceEditorDialog
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
