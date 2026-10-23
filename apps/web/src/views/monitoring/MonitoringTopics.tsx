import { Pause, Play, RefreshCw, Search } from "lucide-react";
import type { FormEvent } from "react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { MonitoringTopic, SavedSearch } from "../../lib/contracts/monitoring";
import { useMessages } from "../../lib/i18n";
import { monitoringMessages } from "../../lib/i18n/monitoring";
import { MonitoringConditions } from "./MonitoringConditions";
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
  const text = useMessages(monitoringMessages);
  const creating = pending.has("create-topic");
  return (
    <>
      <form className="query-toolbar compact-form" onSubmit={onCreate}>
        <input
          value={topicName}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder={text("监控主题名称")}
          aria-label={text("监控主题名称")}
          required
          maxLength={200}
          disabled={creating}
        />
        <select
          value={selectedSavedSearchId}
          onChange={(event) => onSearchChange(event.target.value)}
          aria-label={text("选择已保存检索")}
          required
          disabled={creating || !monitorableSearches.length}
        >
          <option value="" disabled>
            {monitorableSearches.length ? text("选择已保存检索") : text("暂无可订阅检索")}
          </option>
          {monitorableSearches.map((saved) => (
            <option value={saved.id} key={saved.id}>
              {saved.name}
            </option>
          ))}
        </select>
        <button
          className="primary-button"
          type="submit"
          disabled={!topicName.trim() || !selectedSavedSearchId || creating}
        >
          {creating ? text("创建中") : text("创建主题")}
        </button>
      </form>
      {topics.length ? (
        <ScrollableTableRegion ariaLabel={text("监控主题")} className="monitoring-records">
          <table aria-label={text("监控主题")}>
            <thead>
              <tr>
                <th>{text("主题")}</th>
                <th>{text("检索条件")}</th>
                <th>{text("状态")}</th>
                <th>{text("更新时间")}</th>
                <th aria-label={text("操作")} />
              </tr>
            </thead>
            <tbody>
              {topics.map((topic) => {
                const saved = searches.find((item) => item.id === topic.saved_search_id);
                const summary = saved && saved.query_version === topic.query_version ? savedSearchSummary(saved) : null;
                const busy = pending.has(`topic:${topic.id}`) || pending.has(`replay:topic:${topic.id}`);
                return (
                  <tr key={topic.id}>
                    <td className="monitoring-record-name" data-label={text("主题")}>
                      <strong>{topic.name}</strong>
                    </td>
                    <td className="monitoring-record-body" data-label={text("检索条件")}>
                      {saved?.name ?? text("不可用")}
                      <MonitoringConditions conditions={summary?.conditions ?? []} />
                      <small className="cell-subtitle">
                        {text("固定于 v{version}", { version: topic.query_version })}
                      </small>
                      {saved && saved.query_version !== topic.query_version ? (
                        <small className="cell-subtitle">{text("已保存检索有新版本；本主题仍按固定版本运行")}</small>
                      ) : null}
                    </td>
                    <td className="monitoring-record-meta" data-label={text("状态")}>
                      <StatusBadge
                        value={topic.active ? "active" : "paused"}
                        label={topic.active ? text("监控中") : text("已暂停")}
                      />
                    </td>
                    <td className="monitoring-record-meta" data-label={text("更新时间")}>
                      {formatDate(topic.updated_at)}
                    </td>
                    <td className="monitoring-record-actions">
                      <div className="row-actions">
                        {saved ? (
                          <>
                            <button
                              className="icon-button"
                              type="button"
                              title={text("运行固定检索")}
                              aria-label={text("运行 {name} 固定检索", { name: topic.name })}
                              disabled={busy}
                              aria-busy={pending.has(`replay:topic:${topic.id}`) || undefined}
                              onClick={() => onReplay(topic.id)}
                            >
                              <Search size={16} aria-hidden="true" />
                              <span className="monitoring-action-label">{text("运行")}</span>
                            </button>
                            {saved.query_version !== topic.query_version ? (
                              <button
                                className="icon-button"
                                type="button"
                                title={text("同步到检索 v{version}", { version: saved.query_version })}
                                aria-label={text("同步 {name} 到检索 v{version}", {
                                  name: topic.name,
                                  version: saved.query_version,
                                })}
                                disabled={busy}
                                onClick={() => onSync(topic, saved.query_version)}
                              >
                                <RefreshCw size={16} aria-hidden="true" />
                                <span className="monitoring-action-label">{text("同步版本")}</span>
                              </button>
                            ) : null}
                          </>
                        ) : null}
                        <button
                          className="icon-button"
                          type="button"
                          title={topic.active ? text("暂停监控") : text("恢复监控")}
                          aria-label={
                            topic.active
                              ? text("暂停 {name}", { name: topic.name })
                              : text("恢复 {name}", { name: topic.name })
                          }
                          disabled={busy}
                          onClick={() => onToggle(topic)}
                        >
                          {topic.active ? (
                            <Pause size={16} aria-hidden="true" />
                          ) : (
                            <Play size={16} aria-hidden="true" />
                          )}
                          <span className="monitoring-action-label">{topic.active ? text("暂停") : text("恢复")}</span>
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
        <EmptyState
          title={text("暂无监控主题")}
          detail={text("先保存检索条件，再创建持续监控主题；结构检索暂不支持变更订阅")}
        />
      )}
    </>
  );
}
