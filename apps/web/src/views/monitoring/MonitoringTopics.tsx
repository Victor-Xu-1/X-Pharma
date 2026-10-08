import { Pause, Play, RefreshCw, Search } from "lucide-react";
import type { FormEvent } from "react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { MonitoringTopic, SavedSearch } from "../../lib/contracts/monitoring";
import { savedSearchSummary } from "./savedSearchPresentation";

export function MonitoringTopics({
  topics,
  searches,
  monitorableSearches,
  topicName,
  selectedSavedSearchId,
  pending,
  onNameChange,
  onSearchChange,
  onCreate,
  onReplay,
  onSync,
  onToggle,
}: {
  topics: MonitoringTopic[];
  searches: SavedSearch[];
  monitorableSearches: SavedSearch[];
  topicName: string;
  selectedSavedSearchId: string;
  pending: ReadonlySet<string>;
  onNameChange: (name: string) => void;
  onSearchChange: (id: string) => void;
  onCreate: (event: FormEvent) => void;
  onReplay: (id: string) => void;
  onSync: (topic: MonitoringTopic, version: number) => void;
  onToggle: (topic: MonitoringTopic) => void;
}) {
  const creating = pending.has("create-topic");
  return (
    <>
      <form className="query-toolbar compact-form" onSubmit={onCreate}>
        <input
          value={topicName}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder="监控主题名称"
          aria-label="监控主题名称"
          required
          maxLength={200}
          disabled={creating}
        />
        <select
          value={selectedSavedSearchId}
          onChange={(event) => onSearchChange(event.target.value)}
          aria-label="选择已保存检索"
          required
          disabled={creating || !monitorableSearches.length}
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
          disabled={!topicName.trim() || !selectedSavedSearchId || creating}
        >
          {creating ? "创建中" : "创建主题"}
        </button>
      </form>
      {topics.length ? (
        <ScrollableTableRegion ariaLabel="监控主题" className="monitoring-records">
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
                const summary = saved && saved.query_version === topic.query_version ? savedSearchSummary(saved) : null;
                const busy = pending.has(`topic:${topic.id}`) || pending.has(`replay:topic:${topic.id}`);
                return (
                  <tr key={topic.id}>
                    <td className="monitoring-record-name" data-label="主题">
                      <strong>{topic.name}</strong>
                    </td>
                    <td className="monitoring-record-body" data-label="检索条件">
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
                    <td className="monitoring-record-meta" data-label="状态">
                      <StatusBadge
                        value={topic.active ? "active" : "paused"}
                        label={topic.active ? "监控中" : "已暂停"}
                      />
                    </td>
                    <td className="monitoring-record-meta" data-label="更新时间">
                      {formatDate(topic.updated_at)}
                    </td>
                    <td className="monitoring-record-actions">
                      <div className="row-actions">
                        {saved ? (
                          <>
                            <button
                              className="icon-button"
                              type="button"
                              title="运行固定检索"
                              aria-label={`运行 ${topic.name} 固定检索`}
                              disabled={busy}
                              aria-busy={pending.has(`replay:topic:${topic.id}`) || undefined}
                              onClick={() => onReplay(topic.id)}
                            >
                              <Search size={16} aria-hidden="true" />
                              <span className="monitoring-action-label">运行</span>
                            </button>
                            {saved.query_version !== topic.query_version ? (
                              <button
                                className="icon-button"
                                type="button"
                                title={`同步到检索 v${saved.query_version}`}
                                aria-label={`同步 ${topic.name} 到检索 v${saved.query_version}`}
                                disabled={busy}
                                onClick={() => onSync(topic, saved.query_version)}
                              >
                                <RefreshCw size={16} aria-hidden="true" />
                                <span className="monitoring-action-label">同步版本</span>
                              </button>
                            ) : null}
                          </>
                        ) : null}
                        <button
                          className="icon-button"
                          type="button"
                          title={topic.active ? "暂停监控" : "恢复监控"}
                          aria-label={topic.active ? `暂停 ${topic.name}` : `恢复 ${topic.name}`}
                          disabled={busy}
                          onClick={() => onToggle(topic)}
                        >
                          {topic.active ? (
                            <Pause size={16} aria-hidden="true" />
                          ) : (
                            <Play size={16} aria-hidden="true" />
                          )}
                          <span className="monitoring-action-label">{topic.active ? "暂停" : "恢复"}</span>
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
        <EmptyState title="暂无监控主题" detail="先保存检索条件，再创建持续监控主题；结构检索暂不支持变更订阅" />
      )}
    </>
  );
}
