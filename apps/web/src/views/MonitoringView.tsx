import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  Bookmark,
  Check,
  ExternalLink,
  LockKeyhole,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Search,
  Share2,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../components/common";
import { ResearchMetadataDialog } from "../components/ResearchMetadataDialog";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import type { MonitoringAlert, MonitoringSnapshot, MonitoringTopic, SavedSearch } from "../lib/contracts/monitoring";
import {
  createMonitoringTopic,
  loadMonitoring,
  markMonitoringAlertRead,
  monitoringKeys,
  setMonitoringTopicActive,
  setMonitoringTopicQueryVersion,
  setSavedSearchVisibility,
  updateSavedSearchMetadata,
} from "../lib/contracts/monitoring";
import type { User } from "../lib/types";
import type { MonitoringTab } from "../lib/workspaceRouting";
import { savedSearchSummary } from "./monitoring/savedSearchPresentation";
import { useMonitoringOperations } from "./monitoring/useMonitoringOperations";

type Tab = MonitoringTab;

const monitoringTabs: ReadonlyArray<ResearchTabOption<Tab>> = [
  { key: "alerts", label: "提醒中心", icon: <Bell size={16} aria-hidden="true" /> },
  { key: "topics", label: "监控主题", icon: <Play size={16} aria-hidden="true" /> },
  { key: "searches", label: "已保存检索", icon: <Bookmark size={16} aria-hidden="true" /> },
];

export function MonitoringView({
  activeTab,
  onOpenEntity,
  onOpenSearch,
  onTabChange,
  user,
}: {
  activeTab?: MonitoringTab;
  onOpenEntity: (entityId: string) => void;
  onOpenSearch: (saved: SavedSearch) => void;
  onTabChange?: (tab: MonitoringTab) => void;
  user: User;
}) {
  const queryClient = useQueryClient();
  const [localTab, setLocalTab] = useState<Tab>("alerts");
  const tab = activeTab ?? localTab;
  const handleTabChange = onTabChange ?? ((nextTab: Tab) => setLocalTab(nextTab));
  const operations = useMonitoringOperations(tab, onOpenSearch);
  const [topicName, setTopicName] = useState("");
  const [savedSearchId, setSavedSearchId] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [editingSavedSearch, setEditingSavedSearch] = useState<SavedSearch | null>(null);
  const [editorName, setEditorName] = useState("");
  const [editorDescription, setEditorDescription] = useState("");
  const [editorPending, setEditorPending] = useState(false);
  const [editorError, setEditorError] = useState("");
  const queryKey = monitoringKeys.all(unreadOnly);
  const monitoring = useQuery({
    queryKey,
    queryFn: ({ signal }) => loadMonitoring(unreadOnly, signal),
  });
  const searches = monitoring.data?.searches ?? [];
  const monitorableSearches = searches.filter((saved) => saved.query_type !== "chemistry_search");
  const topics = monitoring.data?.topics ?? [];
  const alerts = monitoring.data?.alerts ?? [];
  const selectedSavedSearchId = savedSearchId || monitorableSearches[0]?.id || "";
  const queryError = monitoring.error instanceof Error ? monitoring.error.message : "";
  const error = operations.error || queryError;

  async function load() {
    operations.clearError();
    await monitoring.refetch();
  }

  async function createTopic(event: FormEvent) {
    event.preventDefault();
    await operations.run(
      "create-topic",
      () =>
        createMonitoringTopic({
          name: topicName,
          saved_search_id: selectedSavedSearchId,
        }),
      async () => {
        setTopicName("");
        await load();
      },
    );
  }

  async function toggleTopic(topic: MonitoringTopic) {
    await operations.run(`topic:${topic.id}`, () => setMonitoringTopicActive(topic.id, !topic.active), load);
  }

  async function syncTopicQuery(topic: MonitoringTopic, queryVersion: number) {
    await operations.run(`topic:${topic.id}`, () => setMonitoringTopicQueryVersion(topic.id, queryVersion), load);
  }

  async function markRead(alert: MonitoringAlert) {
    await operations.run(
      `read:${alert.id}`,
      () => markMonitoringAlertRead(alert.id),
      () => {
        queryClient.setQueryData<MonitoringSnapshot>(queryKey, (current) =>
          current
            ? {
                ...current,
                alerts: unreadOnly
                  ? current.alerts.filter((item) => item.id !== alert.id)
                  : current.alerts.map((item) =>
                      item.id === alert.id ? { ...item, read_at: new Date().toISOString() } : item,
                    ),
              }
            : current,
        );
      },
    );
  }

  async function toggleSavedSearchVisibility(saved: SavedSearch) {
    await operations.run(
      `saved:${saved.id}`,
      () => setSavedSearchVisibility(saved.id, saved.visibility === "tenant" ? "private" : "tenant"),
      load,
    );
  }

  function openSavedSearchEditor(saved: SavedSearch) {
    setEditingSavedSearch(saved);
    setEditorName(saved.name);
    setEditorDescription(saved.description);
    setEditorError("");
  }

  function closeSavedSearchEditor() {
    if (editorPending) return;
    setEditingSavedSearch(null);
    setEditorError("");
  }

  async function saveSavedSearchMetadata(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingSavedSearch || !editorName.trim()) return;
    setEditorPending(true);
    setEditorError("");
    try {
      await updateSavedSearchMetadata(editingSavedSearch.id, {
        name: editorName.trim(),
        description: editorDescription.trim(),
      });
      await load();
      setEditingSavedSearch(null);
    } catch (caught) {
      setEditorError(caught instanceof Error ? caught.message : "已保存检索更新失败");
    } finally {
      setEditorPending(false);
    }
  }

  if (monitoring.isPending) return <Spinner label="正在加载情报监控" />;
  if (error && !searches.length && !topics.length && !alerts.length)
    return <ErrorState message={error} retry={() => void load()} />;

  return (
    <section className="data-section monitoring-section">
      <ResearchTabList
        tabs={monitoringTabs}
        activeTab={tab}
        onChange={handleTabChange}
        ariaLabel="监控视图"
        idPrefix="monitoring"
        className="view-tabs"
      />
      {error ? (
        <div className="inline-error" role="alert">
          <span>{error}</span>
          <button className="text-button" type="button" onClick={() => void load()} disabled={monitoring.isFetching}>
            {monitoring.isFetching ? "重试中" : "重试"}
          </button>
        </div>
      ) : null}

      {tab === "alerts" ? (
        <section id="monitoring-panel-alerts" role="tabpanel" aria-labelledby="monitoring-tab-alerts">
          <div className="section-toolbar">
            <label className="check-control">
              <input type="checkbox" checked={unreadOnly} onChange={(event) => setUnreadOnly(event.target.checked)} />
              仅看未读
            </label>
            <span>{alerts.filter((item) => !item.read_at).length} 条未读</span>
          </div>
          {alerts.length ? (
            <ScrollableTableRegion ariaLabel="情报提醒">
              <table aria-label="情报提醒">
                <thead>
                  <tr>
                    <th>主题</th>
                    <th>变更实体</th>
                    <th>摘要</th>
                    <th>发生时间</th>
                    <th>状态</th>
                    <th aria-label="操作" />
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((alert) => (
                    <tr key={alert.id}>
                      <td>{alert.topic_name}</td>
                      <td>
                        <strong>{alert.entity_name}</strong>
                      </td>
                      <td>{alert.summary}</td>
                      <td>{formatDate(alert.occurred_at)}</td>
                      <td>
                        <StatusBadge value={alert.read_at ? "read" : "unread"} />
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="icon-button"
                            type="button"
                            title="打开实体"
                            aria-label={`打开 ${alert.entity_name}`}
                            onClick={() => onOpenEntity(alert.entity_id)}
                          >
                            <ExternalLink size={16} />
                          </button>
                          <button
                            className="icon-button"
                            type="button"
                            title="重放事件产生时的原始检索条件"
                            aria-label={`重放 ${alert.topic_name} 监控检索`}
                            disabled={operations.pending.has(`replay:alert:${alert.id}`)}
                            onClick={() => void operations.replay("alert", alert.id)}
                          >
                            <Search size={16} />
                          </button>
                          {!alert.read_at ? (
                            <button
                              className="icon-button"
                              type="button"
                              title="标记已读"
                              aria-label={`将 ${alert.entity_name} 提醒标记已读`}
                              disabled={operations.pending.has(`read:${alert.id}`)}
                              onClick={() => void markRead(alert)}
                            >
                              <Check size={16} />
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollableTableRegion>
          ) : (
            <EmptyState title="暂无变更提醒" detail="已启用的监控主题将在数据变化时生成提醒" />
          )}
        </section>
      ) : null}

      {tab === "topics" ? (
        <section id="monitoring-panel-topics" role="tabpanel" aria-labelledby="monitoring-tab-topics">
          <form className="query-toolbar compact-form" onSubmit={(event) => void createTopic(event)}>
            <input
              value={topicName}
              onChange={(event) => setTopicName(event.target.value)}
              placeholder="监控主题名称"
              aria-label="监控主题名称"
              required
              disabled={operations.pending.has("create-topic")}
            />
            <select
              value={selectedSavedSearchId}
              onChange={(event) => setSavedSearchId(event.target.value)}
              aria-label="选择已保存检索"
              required
              disabled={operations.pending.has("create-topic")}
            >
              <option value="" disabled>
                选择已保存检索
              </option>
              {monitorableSearches.length ? (
                monitorableSearches.map((saved) => (
                  <option value={saved.id} key={saved.id}>
                    {saved.name}
                  </option>
                ))
              ) : (
                <option value="" disabled>
                  暂无可订阅检索
                </option>
              )}
            </select>
            <button
              className="primary-button"
              type="submit"
              disabled={!topicName.trim() || !selectedSavedSearchId || operations.pending.has("create-topic")}
            >
              {operations.pending.has("create-topic") ? "创建中" : "创建主题"}
            </button>
          </form>
          {topics.length ? (
            <ScrollableTableRegion ariaLabel="监控主题">
              <table aria-label="监控主题">
                <thead>
                  <tr>
                    <th>主题</th>
                    <th>检索条件</th>
                    <th>状态</th>
                    <th>更新时间</th>
                    <th aria-label="操作" />
                  </tr>
                </thead>
                <tbody>
                  {topics.map((topic) => {
                    const saved = searches.find((item) => item.id === topic.saved_search_id);
                    const summary =
                      saved && saved.query_version === topic.query_version ? savedSearchSummary(saved) : null;
                    return (
                      <tr key={topic.id}>
                        <td>
                          <strong>{topic.name}</strong>
                        </td>
                        <td>
                          {saved?.name ?? "不可用"}
                          {summary?.conditions.length ? (
                            <small className="cell-subtitle" title={summary.conditions.join(" · ")}>
                              条件：{summary.conditions.join(" · ")}
                            </small>
                          ) : null}
                          <small className="cell-subtitle">固定于 v{topic.query_version}</small>
                          {saved && saved.query_version !== topic.query_version ? (
                            <small className="cell-subtitle">已保存检索有新版本；本主题仍按固定版本运行</small>
                          ) : null}
                        </td>
                        <td>
                          <StatusBadge value={topic.active ? "active" : "paused"} />
                        </td>
                        <td>{formatDate(topic.updated_at)}</td>
                        <td>
                          <div className="row-actions">
                            {(() => {
                              if (!saved) return null;
                              return (
                                <>
                                  <button
                                    className="icon-button"
                                    type="button"
                                    title="运行固定检索"
                                    aria-label={`运行 ${topic.name} 固定检索`}
                                    disabled={
                                      operations.pending.has(`replay:topic:${topic.id}`) ||
                                      operations.pending.has(`topic:${topic.id}`)
                                    }
                                    onClick={() => void operations.replay("topic", topic.id)}
                                  >
                                    <Search size={16} />
                                  </button>
                                  {saved.query_version !== topic.query_version ? (
                                    <button
                                      className="icon-button"
                                      type="button"
                                      title={`同步到检索 v${saved.query_version}`}
                                      aria-label={`同步 ${topic.name} 到检索 v${saved.query_version}`}
                                      disabled={
                                        operations.pending.has(`topic:${topic.id}`) ||
                                        operations.pending.has(`replay:topic:${topic.id}`)
                                      }
                                      onClick={() => void syncTopicQuery(topic, saved.query_version)}
                                    >
                                      <RefreshCw size={16} />
                                    </button>
                                  ) : null}
                                </>
                              );
                            })()}
                            <button
                              className="icon-button"
                              type="button"
                              title={topic.active ? "暂停监控" : "恢复监控"}
                              aria-label={topic.active ? `暂停 ${topic.name}` : `恢复 ${topic.name}`}
                              onClick={() => void toggleTopic(topic)}
                              disabled={
                                operations.pending.has(`topic:${topic.id}`) ||
                                operations.pending.has(`replay:topic:${topic.id}`)
                              }
                            >
                              {topic.active ? <Pause size={16} /> : <Play size={16} />}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </ScrollableTableRegion>
          ) : (
            <EmptyState title="暂无监控主题" detail="先保存检索条件，再创建持续监控主题" />
          )}
        </section>
      ) : null}

      {tab === "searches" ? (
        <section id="monitoring-panel-searches" role="tabpanel" aria-labelledby="monitoring-tab-searches">
          {searches.length ? (
            <ScrollableTableRegion ariaLabel="已保存检索">
              <table aria-label="已保存检索">
                <thead>
                  <tr>
                    <th>名称</th>
                    <th>查询</th>
                    <th>类型</th>
                    <th>共享范围</th>
                    <th>版本</th>
                    <th>更新时间</th>
                    <th aria-label="操作" />
                  </tr>
                </thead>
                <tbody>
                  {searches.map((saved) => {
                    const summary = savedSearchSummary(saved);
                    return (
                      <tr key={saved.id}>
                        <td>
                          <strong>{saved.name}</strong>
                          <small className="cell-subtitle">{saved.description}</small>
                        </td>
                        <td>
                          {summary.query}
                          {summary.conditions.length ? (
                            <small className="cell-subtitle" title={summary.conditions.join(" · ")}>
                              条件：{summary.conditions.join(" · ")}
                            </small>
                          ) : null}
                        </td>
                        <td>
                          {summary.type}
                          <small className="cell-subtitle">{summary.view}</small>
                        </td>
                        <td>
                          {saved.visibility === "tenant" ? "企业共享" : "仅自己"}
                          {saved.owner_user_id !== user.id ? (
                            <small className="cell-subtitle">共享给你的只读检索</small>
                          ) : null}
                        </td>
                        <td>v{saved.query_version}</td>
                        <td>{formatDate(saved.updated_at)}</td>
                        <td>
                          <div className="row-actions">
                            <button
                              className="icon-button"
                              type="button"
                              title="运行已保存检索"
                              aria-label={`运行 ${saved.name}`}
                              onClick={() => onOpenSearch(saved)}
                            >
                              <Search size={16} />
                            </button>
                            {saved.owner_user_id === user.id ? (
                              <>
                                <button
                                  className="icon-button"
                                  type="button"
                                  title="编辑名称与业务说明"
                                  aria-label={`编辑 ${saved.name}`}
                                  onClick={() => openSavedSearchEditor(saved)}
                                >
                                  <Pencil size={16} />
                                </button>
                                <button
                                  className="icon-button"
                                  type="button"
                                  disabled={operations.pending.has(`saved:${saved.id}`)}
                                  title={saved.visibility === "tenant" ? "撤回企业共享" : "共享给企业成员"}
                                  aria-label={
                                    saved.visibility === "tenant" ? `将 ${saved.name} 设为私有` : `共享 ${saved.name}`
                                  }
                                  onClick={() => void toggleSavedSearchVisibility(saved)}
                                >
                                  {saved.visibility === "tenant" ? <LockKeyhole size={16} /> : <Share2 size={16} />}
                                </button>
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </ScrollableTableRegion>
          ) : (
            <EmptyState title="暂无已保存检索" detail="在情报检索页保存常用条件" />
          )}
        </section>
      ) : null}
      <ResearchMetadataDialog
        title="编辑已保存检索"
        open={editingSavedSearch !== null}
        name={editorName}
        description={editorDescription}
        pending={editorPending}
        error={editorError}
        onNameChange={setEditorName}
        onDescriptionChange={setEditorDescription}
        onClose={closeSavedSearchEditor}
        onSubmit={(event) => void saveSavedSearchMetadata(event)}
      />
    </section>
  );
}
