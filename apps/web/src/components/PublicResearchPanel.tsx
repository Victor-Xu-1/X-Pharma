import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { loadPublicCoverage, type PublicResearchTopic, searchPublicResearch } from "../lib/contracts/publicResearch";
import { entityLabels } from "../lib/entityPresentation";
import { useFilterDraft } from "../lib/useFilterDraft";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import { ErrorState, Spinner } from "./common";
import { PublicResearchResults } from "./PublicResearchResults";

const topics: ReadonlyArray<readonly [PublicResearchTopic, string]> = [
  ["overview", "综合调研"],
  ["drugs", "药物"],
  ["targets", "靶点"],
  ["trials", "临床试验"],
  ["organizations", "试验申办方"],
  ["conditions", "研究条件"],
  ["patents", "关键词专利（历史著录）"],
  ["compound_patents", "化合物专利引用（药物名/CID）"],
  ["literature", "文献"],
  ["disclosures", "公司公告／交易线索"],
];

export function PublicResearchPanel({
  defaultQuery = "",
  defaultTopic = "overview",
}: {
  defaultQuery?: string;
  defaultTopic?: PublicResearchTopic;
}) {
  const inputId = useId();
  const [expanded, setExpanded] = useState(false);
  const [draft, setDraft] = useFilterDraft({ q: defaultQuery, topic: defaultTopic });
  const [executed, setExecuted] = useState<{ q: string; topic: PublicResearchTopic; request: number } | null>(null);
  const coverage = useQuery({
    queryKey: ["public-research", "coverage"],
    queryFn: ({ signal }) => loadPublicCoverage(signal),
    enabled: expanded,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
  });
  const queryKey = ["public-research", "search", inputId, executed] as const;
  const search = useQuery({
    queryKey,
    queryFn: ({ signal }) => {
      if (!executed) throw new Error("公开检索尚未执行");
      return searchPublicResearch({ q: executed.q, topic: executed.topic, limit: 10 }, signal);
    },
    enabled: Boolean(executed),
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: Infinity,
  });
  const cancellation = useQueryCancellation(queryKey);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!draft.q.trim() || draft.q.trim().length > 120 || search.isFetching) return;
    cancellation.reset();
    setExecuted((previous) => ({ q: draft.q.trim(), topic: draft.topic, request: (previous?.request ?? 0) + 1 }));
  }

  return (
    <details
      className="advanced-filters"
      data-testid="public-research-panel"
      onToggle={(event) => {
        setExpanded(event.currentTarget.open);
      }}
    >
      <summary>
        公开来源调研<span>补充本地覆盖 · 按需联网查询</span>
      </summary>
      <section aria-label="公开来源调研">
        <details>
          <summary>查看本地数据覆盖</summary>
          {coverage.isFetching ? <Spinner label="正在读取本地覆盖" /> : null}
          {coverage.error ? <ErrorState message="本地覆盖读取失败" /> : null}
          {coverage.data ? (
            <>
              <p>
                {Object.entries(coverage.data.entity_counts)
                  .filter(([type]) =>
                    ["drug", "target", "organization", "disease", "clinical_trial", "patent", "transaction"].includes(
                      type,
                    ),
                  )
                  .map(([type, count]) => `${entityLabels[type] ?? type} ${count}`)
                  .join(" · ")}
              </p>
              <p>{coverage.data.scope_note}</p>
              <p>已登记公开来源：{coverage.data.public_source_names.join("、") || "未登记"}</p>
            </>
          ) : null}
          <button
            className="secondary-button"
            type="button"
            onClick={() => void coverage.refetch()}
            disabled={coverage.isFetching}
          >
            刷新本地覆盖
          </button>
        </details>
        <p>
          仅点击“查询公开来源”后才发送下方关键词。不要输入患者、未公开项目或其他保密信息；联网结果与本地已核验数据分开。
        </p>
        <form className="intelligence-query-panel" onSubmit={submit} aria-label="公开来源检索">
          <div className="query-row">
            <label htmlFor={inputId}>公开关键词</label>
            <input
              id={inputId}
              value={draft.q}
              maxLength={120}
              onChange={(event) => setDraft({ ...draft, q: event.target.value })}
              placeholder="英文靶点、药物、公司或研究主题"
            />
            <label htmlFor={`${inputId}-topic`}>调研范围</label>
            <select
              id={`${inputId}-topic`}
              value={draft.topic}
              onChange={(event) => setDraft({ ...draft, topic: event.target.value as PublicResearchTopic })}
            >
              {topics.map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
            <button
              className="primary-button"
              type="submit"
              disabled={!draft.q.trim() || draft.q.trim().length > 120 || search.isFetching}
            >
              查询公开来源
            </button>
          </div>
        </form>
        {search.isFetching ? (
          <>
            <Spinner label="正在查询公开来源" />
            <button className="secondary-button" type="button" onClick={cancellation.cancel}>
              取消等待
            </button>
          </>
        ) : null}
        {cancellation.isCancelled ? (
          <p role="status">已取消本次等待；来源请求将在有界时限内结束，未写入本地事实。</p>
        ) : null}
        {search.error ? (
          <ErrorState message={search.error instanceof Error ? search.error.message : "公开查询失败，请明确重试"} />
        ) : null}
        {search.data ? <PublicResearchResults response={search.data} /> : null}
      </section>
    </details>
  );
}
