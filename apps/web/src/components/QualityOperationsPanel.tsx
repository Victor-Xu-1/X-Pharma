import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError } from "../lib/api";
import {
  actOnDataQualityIssue,
  type DataQualityIssue,
  evaluateDataQuality,
  governanceKeys,
  loadDataQualityCoverage,
  loadDataQualityIssueEvents,
  loadDataQualityIssues,
  loadDataQualityOwners,
  loadDataQualitySnapshots,
} from "../lib/contracts/governance";
import { useLocale } from "../lib/i18n";
import { governanceQualityText as t } from "../lib/i18n/governanceQuality";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge, statusLabel } from "./common";
import { QualityMetricCards } from "./quality/QualityMetricCards";
import { qualityPercent } from "./quality/qualityMetricPresentation";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

const METRIC_ORDER = [
  "completeness",
  "duplicate_rate",
  "citation_coverage",
  "freshness_coverage",
  "ingestion_success",
  "drift",
] as const;
const ACTIVE_STATUSES = new Set(["open", "acknowledged", "ready_to_resolve"]);
const ACTOR_LABELS: Record<string, string> = {
  agent: "Agent",
  api_key: "API 客户端",
  system: "系统",
  user: "用户",
};

export function QualityOperationsPanel() {
  useLocale();
  const [issueStatus, setIssueStatus] = useState("all");
  const [selectedIssueId, setSelectedIssueId] = useState("");
  const [ownerUserId, setOwnerUserId] = useState("");
  const [actionNotes, setActionNotes] = useState("");
  const snapshots = useQuery({
    queryKey: governanceKeys.qualitySnapshots,
    queryFn: ({ signal }) => loadDataQualitySnapshots(signal),
  });
  const coverage = useQuery({
    queryKey: governanceKeys.qualityCoverage,
    queryFn: ({ signal }) => loadDataQualityCoverage(signal),
  });
  const issues = useQuery({
    queryKey: governanceKeys.qualityIssues(issueStatus),
    queryFn: ({ signal }) => loadDataQualityIssues(issueStatus, signal),
  });
  const owners = useQuery({
    queryKey: governanceKeys.qualityOwners,
    queryFn: ({ signal }) => loadDataQualityOwners(signal),
  });
  const selectedIssue = (issues.data ?? []).find((issue) => issue.id === selectedIssueId) ?? issues.data?.[0] ?? null;
  const events = useQuery({
    queryKey: governanceKeys.qualityIssueEvents(selectedIssue?.id ?? "none"),
    queryFn: ({ signal }) => loadDataQualityIssueEvents(selectedIssue?.id ?? "", signal),
    enabled: Boolean(selectedIssue),
  });
  const evaluation = useMutation({
    mutationFn: evaluateDataQuality,
    onSuccess: async () => {
      await Promise.all([snapshots.refetch(), issues.refetch()]);
    },
  });
  const action = useMutation({
    mutationFn: actOnDataQualityIssue,
    onSuccess: async () => {
      setActionNotes("");
      await Promise.all([issues.refetch(), events.refetch()]);
    },
  });

  useEffect(() => {
    setOwnerUserId(selectedIssue?.owner_user_id ?? "");
  }, [selectedIssue?.owner_user_id]);

  const snapshotDenied = snapshots.error instanceof ApiError && [401, 403].includes(snapshots.error.status);
  const snapshotData = snapshotDenied ? undefined : snapshots.data;
  const latest = snapshotData?.[0] ?? null;
  const trend = [...(snapshotData ?? [])].slice(0, 12).reverse();
  const activeQualityIssues = (issues.data ?? []).filter((issue) => ACTIVE_STATUSES.has(issue.status));
  const overdueQualityIssues = activeQualityIssues.filter((issue) => new Date(issue.sla_due_at).getTime() < Date.now());
  const error =
    (coverage.error instanceof Error ? coverage.error.message : "") ||
    (issues.error instanceof Error ? issues.error.message : "") ||
    (owners.error instanceof Error ? owners.error.message : "") ||
    (evaluation.error instanceof Error ? evaluation.error.message : "") ||
    (action.error instanceof Error ? action.error.message : "");

  function submitIssueAction(issue: DataQualityIssue, requestedAction: "assign" | "acknowledge" | "resolve" | "waive") {
    action.mutate({
      issueId: issue.id,
      action: requestedAction,
      expected_version: issue.version,
      owner_user_id: requestedAction === "assign" ? ownerUserId || null : null,
      notes: actionNotes.trim() || null,
    });
  }

  return (
    <div className="quality-operations">
      <section className="quality-overview" aria-labelledby="quality-overview-title">
        <header>
          <div>
            <h2 id="quality-overview-title">数据质量运营</h2>
            <p>
              {t("指标定义 {version}", { version: latest?.definitions_version ?? t("未上报") })} ·{" "}
              {t("所有处置写入不可变事件历史。")}
            </p>
          </div>
          <button
            className="primary-button"
            type="button"
            disabled={evaluation.isPending}
            onClick={() => evaluation.mutate()}
          >
            <RotateCcw size={16} />
            立即评估
          </button>
        </header>
        {snapshots.isPending ? <Spinner label={t("正在读取质量快照")} /> : null}
        {snapshots.error instanceof Error ? (
          <ErrorState message={snapshots.error.message} retry={() => void snapshots.refetch()} />
        ) : null}
        {latest ? (
          <QualityMetricCards metrics={latest.metrics} />
        ) : !snapshots.isPending && !snapshots.error ? (
          <EmptyState title={t("尚无质量快照")} detail={t("运行一次评估以建立首个质量基线")} />
        ) : null}
        {activeQualityIssues.length ? (
          <div className="factory-warning" role="status">
            <AlertTriangle size={17} />
            <span>
              <strong>仍有待处置质量事件</strong>
              当前快照之外仍有 {activeQualityIssues.length} 个事件尚未结案
              {overdueQualityIssues.length ? `，其中 ${overdueQualityIssues.length} 个已超过 SLA` : ""}；
              请在下方复核并关闭或记录豁免。
            </span>
          </div>
        ) : null}
      </section>

      <section className="quality-source-coverage" aria-labelledby="quality-source-coverage-title">
        <header>
          <div>
            <h3 id="quality-source-coverage-title">来源覆盖与授权</h3>
            <p>按数据集查看解析缺口、事实发布、冲突、新鲜度、失败 SLA 和责任人。</p>
          </div>
          <small>{coverage.data?.length ?? 0} 个来源</small>
        </header>
        {coverage.isPending ? <Spinner label="正在读取来源覆盖" /> : null}
        {!coverage.isPending && coverage.data?.length ? (
          <ScrollableTableRegion className="quality-table-scroll" ariaLabel="来源覆盖与授权滚动区域">
            <table aria-label="来源覆盖与授权">
              <thead>
                <tr>
                  <th>来源 / 数据集</th>
                  <th>解析覆盖</th>
                  <th>事实发布</th>
                  <th>新鲜度</th>
                  <th>授权</th>
                  <th>失败 SLA</th>
                </tr>
              </thead>
              <tbody>
                {coverage.data.map((source) => (
                  <tr key={source.source_id}>
                    <td>
                      <strong>{source.name}</strong>
                      <small>
                        {source.dataset_key} · {source.owner}
                      </small>
                    </td>
                    <td>
                      <strong>{(source.parse_coverage * 100).toFixed(1)}%</strong>
                      <small>
                        {source.parsed_asset_count}/{source.active_asset_count} · 缺 {source.parse_missing_count}
                      </small>
                    </td>
                    <td>
                      <strong>{(source.published_fact_coverage * 100).toFixed(1)}%</strong>
                      <small>
                        {source.published_fact_count}/{source.fact_count} · 冲突{" "}
                        {(source.conflict_rate * 100).toFixed(1)}%
                      </small>
                    </td>
                    <td>
                      <StatusBadge value={source.freshness_status} />
                      <small>
                        {source.freshness_age_seconds == null ? "尚无成功运行" : `${source.freshness_age_seconds}s`}
                      </small>
                    </td>
                    <td>
                      <StatusBadge value={source.authorization_status} />
                      <small>
                        {source.authorization_scopes.length ? source.authorization_scopes.join("、") : "无范围"}
                      </small>
                    </td>
                    <td>
                      <StatusBadge value={source.failure_sla_status} />
                      <small>{source.consecutive_failures} 次连续失败</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : null}
        {!coverage.isPending && !coverage.data?.length ? (
          <EmptyState title="尚无注册来源" detail="来源接入后将在这里显示质量和授权状态。" />
        ) : null}
      </section>

      <section className="quality-trend" aria-labelledby="quality-trend-title">
        <header>
          <h3 id="quality-trend-title">最近 12 次趋势</h3>
          <small>{latest ? `最近评估 ${formatDate(latest.measured_at, true)}` : "等待首个快照"}</small>
        </header>
        {trend.length ? (
          <ScrollableTableRegion className="quality-table-scroll" ariaLabel="数据质量历史趋势滚动区域">
            <table aria-label="数据质量历史趋势">
              <thead>
                <tr>
                  <th>评估时间</th>
                  {METRIC_ORDER.map((key) => (
                    <th key={key}>{String(latest?.metrics[key]?.label ?? key)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trend.map((snapshot) => (
                  <tr key={snapshot.id}>
                    <td>{formatDate(snapshot.measured_at, true)}</td>
                    {METRIC_ORDER.map((key) => {
                      const metric = snapshot.metrics[key];
                      return (
                        <td key={key}>
                          {metric
                            ? metric.applicable === false
                              ? t("不适用")
                              : qualityPercent(metric.value)
                            : t("未上报")}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title="趋势尚未建立" detail="评估后按时间呈现质量变化。" />
        )}
      </section>

      <section className="quality-issues" aria-labelledby="quality-issues-title">
        <header>
          <div>
            <h3 id="quality-issues-title">质量事件与 SLA</h3>
            <p>恢复指标只进入待关闭状态，必须由负责人复核后结案。</p>
          </div>
          <label>
            <span>事件状态</span>
            <select
              value={issueStatus}
              onChange={(event) => {
                setIssueStatus(event.target.value);
                setSelectedIssueId("");
                setActionNotes("");
              }}
            >
              <option value="all">全部</option>
              <option value="open">待处置</option>
              <option value="acknowledged">已确认</option>
              <option value="ready_to_resolve">待关闭</option>
              <option value="resolved">已解决</option>
              <option value="waived">已豁免</option>
            </select>
          </label>
        </header>
        <div className="quality-issue-layout">
          <section className="quality-issue-list" aria-label="质量事件列表">
            {issues.isPending ? <Spinner label="正在读取质量事件" /> : null}
            {(issues.data ?? []).map((issue) => {
              const overdue = ACTIVE_STATUSES.has(issue.status) && new Date(issue.sla_due_at).getTime() < Date.now();
              return (
                <button
                  type="button"
                  key={issue.id}
                  className={selectedIssue?.id === issue.id ? "active" : ""}
                  onClick={() => {
                    setSelectedIssueId(issue.id);
                    setActionNotes("");
                  }}
                >
                  <span>
                    <StatusBadge value={issue.severity} />
                    <strong>{issue.title}</strong>
                  </span>
                  <small>
                    {issue.owner_display_name ?? "未分配"} ·{" "}
                    {overdue ? "SLA 已超时" : `SLA ${formatDate(issue.sla_due_at, true)}`}
                  </small>
                </button>
              );
            })}
            {!issues.isPending && !issues.data?.length ? (
              <EmptyState title="没有匹配的质量事件" detail="调整状态筛选或运行新评估。" />
            ) : null}
          </section>
          <div className="quality-issue-detail">
            {selectedIssue ? (
              <>
                <header>
                  <div>
                    <span>
                      <StatusBadge value={selectedIssue.status} />
                      <StatusBadge value={selectedIssue.severity} />
                    </span>
                    <h4>{selectedIssue.title}</h4>
                    <p>{selectedIssue.description}</p>
                  </div>
                  <small>v{selectedIssue.version}</small>
                </header>
                {ACTIVE_STATUSES.has(selectedIssue.status) ? (
                  <div className="quality-issue-actions">
                    <label>
                      <span>负责人</span>
                      <select value={ownerUserId} onChange={(event) => setOwnerUserId(event.target.value)}>
                        <option value="">选择负责人</option>
                        {(owners.data ?? []).map((owner) => (
                          <option key={owner.id} value={owner.id}>
                            {owner.display_name} · {owner.role}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      disabled={!ownerUserId || action.isPending}
                      onClick={() => submitIssueAction(selectedIssue, "assign")}
                    >
                      分配
                    </button>
                    <label className="quality-action-notes">
                      <span>处置说明</span>
                      <textarea
                        rows={3}
                        maxLength={4000}
                        value={actionNotes}
                        onChange={(event) => setActionNotes(event.target.value)}
                      />
                    </label>
                    {selectedIssue.status === "open" ? (
                      <button
                        type="button"
                        disabled={!selectedIssue.owner_user_id || action.isPending}
                        onClick={() => submitIssueAction(selectedIssue, "acknowledge")}
                      >
                        {selectedIssue.owner_user_id ? "确认接手" : "请先分配负责人"}
                      </button>
                    ) : null}
                    {selectedIssue.status === "ready_to_resolve" ? (
                      <button
                        className="primary-button"
                        type="button"
                        disabled={!actionNotes.trim() || action.isPending}
                        onClick={() => submitIssueAction(selectedIssue, "resolve")}
                      >
                        复核并关闭
                      </button>
                    ) : null}
                    <button
                      className="danger-button"
                      type="button"
                      disabled={!actionNotes.trim() || action.isPending}
                      onClick={() => submitIssueAction(selectedIssue, "waive")}
                    >
                      记录豁免
                    </button>
                  </div>
                ) : null}
                <div className="quality-event-history">
                  <h5>不可变处置历史</h5>
                  {events.isPending ? <Spinner label="正在读取处置历史" /> : null}
                  {(events.data ?? []).map((event) => (
                    <article key={event.id}>
                      <span>
                        <strong>{statusLabel(event.action)}</strong>
                        <small>{formatDate(event.occurred_at, true)}</small>
                      </span>
                      <p>
                        {event.previous_status ? statusLabel(event.previous_status) : "-"} →{" "}
                        {statusLabel(event.resulting_status)} · {ACTOR_LABELS[event.actor_type] ?? event.actor_type}
                      </p>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <EmptyState title="选择质量事件" detail="查看责任人、SLA 和完整处置历史。" />
            )}
          </div>
        </div>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
      </section>
    </div>
  );
}
