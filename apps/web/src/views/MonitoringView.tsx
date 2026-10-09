import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Bookmark, Play } from "lucide-react";
import { type FormEvent, useState } from "react";
import { ErrorState, QueryRefreshButton, Spinner } from "../components/common";
import { FormStatus } from "../components/FormStatus";
import { ResearchMetadataDialog } from "../components/ResearchMetadataDialog";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ApiError } from "../lib/api";
import {
  createMonitoringTopic,
  loadMonitoring,
  type MonitoringAlert,
  type MonitoringSnapshot,
  type MonitoringTopic,
  markMonitoringAlertRead,
  monitoringKeys,
  type SavedSearch,
  setMonitoringTopicActive,
  setMonitoringTopicQueryVersion,
  setSavedSearchVisibility,
  updateSavedSearchMetadata,
} from "../lib/contracts/monitoring";
import { useMessages } from "../lib/i18n";
import { monitoringMessages } from "../lib/i18n/monitoring";
import type { User } from "../lib/types";
import type { MonitoringTab } from "../lib/workspaceRouting";
import { MonitoringAlerts } from "./monitoring/MonitoringAlerts";
import { MonitoringSearches } from "./monitoring/MonitoringSearches";
import { MonitoringTopics } from "./monitoring/MonitoringTopics";
import { useMonitoringOperations } from "./monitoring/useMonitoringOperations";
import "./monitoring/MonitoringRecords.css";

const monitoringTabs: ReadonlyArray<ResearchTabOption<MonitoringTab> & { label: keyof typeof monitoringMessages }> = [
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
  const text = useMessages(monitoringMessages);
  const queryClient = useQueryClient();
  const [localTab, setLocalTab] = useState<MonitoringTab>("alerts");
  const tab = activeTab ?? localTab;
  const handleTabChange = onTabChange ?? setLocalTab;
  const operations = useMonitoringOperations(tab, onOpenSearch);
  const [topicName, setTopicName] = useState("");
  const [savedSearchId, setSavedSearchId] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [editingSavedSearch, setEditingSavedSearch] = useState<SavedSearch | null>(null);
  const [editorName, setEditorName] = useState("");
  const [editorDescription, setEditorDescription] = useState("");
  const [editorPending, setEditorPending] = useState(false);
  const [editorError, setEditorError] = useState<{ raw: string } | { fallback: true } | null>(null);
  const queryKey = monitoringKeys.all(unreadOnly);
  const monitoring = useQuery({ queryKey, queryFn: ({ signal }) => loadMonitoring(unreadOnly, signal) });
  const searches = monitoring.data?.searches ?? [];
  const monitorableSearches = searches.filter((saved) => saved.query_type !== "chemistry_search");
  const topics = monitoring.data?.topics ?? [];
  const alerts = monitoring.data?.alerts ?? [];
  const selectedSavedSearchId = savedSearchId
    ? monitorableSearches.some((saved) => saved.id === savedSearchId)
      ? savedSearchId
      : ""
    : (monitorableSearches[0]?.id ?? "");
  const error = operations.error || (monitoring.error instanceof Error ? monitoring.error.message : "");

  async function load() {
    operations.clearError();
    await monitoring.refetch();
  }

  async function createTopic(event: FormEvent) {
    event.preventDefault();
    if (!topicName.trim() || !selectedSavedSearchId) return;
    await operations.run(
      "create-topic",
      () => createMonitoringTopic({ name: topicName.trim(), saved_search_id: selectedSavedSearchId }),
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
    setEditorError(null);
  }

  function closeSavedSearchEditor() {
    if (editorPending) return;
    setEditingSavedSearch(null);
    setEditorError(null);
  }

  async function saveSavedSearchMetadata(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingSavedSearch || !editorName.trim()) return;
    setEditorPending(true);
    setEditorError(null);
    try {
      await updateSavedSearchMetadata(editingSavedSearch.id, {
        name: editorName.trim(),
        description: editorDescription.trim(),
      });
      await load();
      setEditingSavedSearch(null);
    } catch (caught) {
      setEditorError(caught instanceof Error ? { raw: caught.message } : { fallback: true });
    } finally {
      setEditorPending(false);
    }
  }

  if (monitoring.error instanceof ApiError && [401, 403].includes(monitoring.error.status))
    return <ErrorState message={monitoring.error.message} retry={() => void load()} />;
  if (monitoring.isPending) return <Spinner label={text("正在加载情报监控")} />;
  if (error && !searches.length && !topics.length && !alerts.length)
    return <ErrorState message={error} retry={() => void load()} />;
  return (
    <section className="data-section monitoring-section">
      <div className="section-toolbar monitoring-toolbar">
        <ResearchTabList
          tabs={monitoringTabs.map((option) => ({ ...option, label: text(option.label) }))}
          activeTab={tab}
          onChange={handleTabChange}
          ariaLabel={text("监控视图")}
          idPrefix="monitoring"
          className="view-tabs"
        />
        <QueryRefreshButton refreshing={monitoring.isFetching} onRefresh={() => void load()} />
      </div>
      <FormStatus
        pending={[...operations.pending].some((key) => key.startsWith("replay:"))}
        pendingLabel={text("正在核验检索条件与访问权限")}
        error=""
      />
      {error ? (
        <div className="inline-error" role="alert">
          <span>{error}</span>
          {monitoring.isError && monitoring.data ? (
            <span>{text("刷新失败，当前显示上次成功读取的监控记录。")}</span>
          ) : null}
          <button className="text-button" type="button" onClick={() => void load()} disabled={monitoring.isFetching}>
            {monitoring.isFetching ? text("重试中") : text("重试")}
          </button>
        </div>
      ) : null}
      <section id={`monitoring-panel-${tab}`} role="tabpanel" aria-labelledby={`monitoring-tab-${tab}`}>
        {tab === "alerts" ? (
          <MonitoringAlerts
            alerts={alerts}
            unreadOnly={unreadOnly}
            pending={operations.pending}
            onUnreadOnlyChange={setUnreadOnly}
            onOpenEntity={onOpenEntity}
            onReplay={(id) => void operations.replay("alert", id)}
            onMarkRead={(alert) => void markRead(alert)}
          />
        ) : null}
        {tab === "topics" ? (
          <MonitoringTopics
            topics={topics}
            searches={searches}
            monitorableSearches={monitorableSearches}
            topicName={topicName}
            selectedSavedSearchId={selectedSavedSearchId}
            pending={operations.pending}
            onNameChange={setTopicName}
            onSearchChange={setSavedSearchId}
            onCreate={(event) => void createTopic(event)}
            onReplay={(id) => void operations.replay("topic", id)}
            onSync={(topic, version) => void syncTopicQuery(topic, version)}
            onToggle={(topic) => void toggleTopic(topic)}
          />
        ) : null}
        {tab === "searches" ? (
          <MonitoringSearches
            searches={searches}
            userId={user.id}
            pending={operations.pending}
            onReplay={(id) => void operations.replay("saved", id)}
            onEdit={openSavedSearchEditor}
            onVisibilityChange={(saved) => void toggleSavedSearchVisibility(saved)}
          />
        ) : null}
      </section>
      <ResearchMetadataDialog
        title={text("编辑已保存检索")}
        open={editingSavedSearch !== null}
        name={editorName}
        description={editorDescription}
        pending={editorPending}
        error={editorError ? ("raw" in editorError ? editorError.raw : text("已保存检索更新失败")) : ""}
        onNameChange={setEditorName}
        onDescriptionChange={setEditorDescription}
        onClose={closeSavedSearchEditor}
        onSubmit={(event) => void saveSavedSearchMetadata(event)}
      />
    </section>
  );
}
