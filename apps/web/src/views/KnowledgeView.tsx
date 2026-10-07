import { useQuery } from "@tanstack/react-query";
import { BookOpenText, ChevronRight, History, Search, ShieldCheck } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import "./knowledge-pagination.css";
import "../styles/knowledge.css";

import { EmptyState, ErrorState, formatDate, Spinner } from "../components/common";
import { ResearchTabList } from "../components/ResearchTabList";
import { ResultPagination } from "../components/ResultPagination";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import {
  getKnowledgePage,
  getKnowledgePageCoverage,
  getKnowledgePageVersionDiff,
  KNOWLEDGE_PAGE_SIZE,
  knowledgeKeys,
  listKnowledgePageVersions,
  searchKnowledgePages,
} from "../lib/contracts/knowledge";
import { entityLabels } from "../lib/entityPresentation";
import type { KnowledgePanel } from "../lib/workspaceRouting";
import { KnowledgeChangeList } from "./knowledge/KnowledgeChangeList";
import { KnowledgeDocument } from "./knowledge/KnowledgeDocument";
import { knowledgePredicateLabel } from "./knowledge/knowledgeReading";

type KnowledgeLocation = {
  query: string;
  pageId: string | null;
  panel: KnowledgePanel;
  versionNumber: number | null;
  offset: number;
  pageType: string;
  sortBy: "title" | "updated_at";
  sortDirection: "asc" | "desc";
};

function knowledgeTypeLabel(type: string): string {
  return type === "disease"
    ? "疾病/登记条件"
    : (entityLabels[type] ?? { topic: "研究专题", entity: "对象档案" }[type as "topic" | "entity"] ?? type);
}

export function KnowledgeView({
  initialQuery = "",
  initialOffset = 0,
  initialPageType = "",
  initialSortBy = "title",
  initialSortDirection = "asc",
  initialPageId = null,
  initialPanel = "document",
  initialVersionNumber = null,
  invalidPageId = false,
  onLocationChange,
}: {
  initialQuery?: string;
  initialOffset?: number;
  initialPageType?: string;
  initialSortBy?: "title" | "updated_at";
  initialSortDirection?: "asc" | "desc";
  initialPageId?: string | null;
  initialPanel?: KnowledgePanel;
  initialVersionNumber?: number | null;
  invalidPageId?: boolean;
  onLocationChange?: (location: KnowledgeLocation) => void;
}) {
  const controlled = Boolean(onLocationChange);
  const [query, setQuery] = useState(initialQuery);
  const [localLocation, setLocalLocation] = useState<KnowledgeLocation>({
    offset: initialOffset,
    pageType: initialPageType,
    sortBy: initialSortBy,
    sortDirection: initialSortDirection,
    query: initialQuery,
    pageId: initialPageId,
    panel: initialPanel,
    versionNumber: initialVersionNumber,
  });
  const location = controlled
    ? {
        offset: initialOffset,
        pageType: initialPageType,
        sortBy: initialSortBy,
        sortDirection: initialSortDirection,
        query: initialQuery,
        pageId: initialPageId,
        panel: initialPanel,
        versionNumber: initialVersionNumber,
      }
    : localLocation;
  const submittedQuery = location.query;
  const selectedPageId = location.pageId ?? "";
  const panel = location.panel;
  const selectedVersionNumber = location.versionNumber;

  useEffect(() => setQuery(initialQuery), [initialQuery]);

  function updateLocation(next: Partial<KnowledgeLocation>) {
    const resolved = { ...location, ...next };
    if (onLocationChange) onLocationChange(resolved);
    else setLocalLocation(resolved);
  }
  const pagesQuery = useQuery({
    queryKey: knowledgeKeys.pages({
      query: submittedQuery,
      offset: location.offset,
      pageType: location.pageType,
      sortBy: location.sortBy,
      sortDirection: location.sortDirection,
    }),
    queryFn: ({ signal }) =>
      searchKnowledgePages(
        {
          query: submittedQuery,
          offset: location.offset,
          pageType: location.pageType,
          sortBy: location.sortBy,
          sortDirection: location.sortDirection,
        },
        signal,
      ),
  });
  const detailQuery = useQuery({
    queryKey: knowledgeKeys.detail(selectedPageId),
    queryFn: ({ signal }) => getKnowledgePage(selectedPageId, signal),
    enabled: Boolean(selectedPageId),
  });
  const coverageQuery = useQuery({
    queryKey: knowledgeKeys.coverage(selectedPageId),
    queryFn: ({ signal }) => getKnowledgePageCoverage(selectedPageId, signal),
    enabled: Boolean(selectedPageId) && panel === "coverage",
  });
  const versionsQuery = useQuery({
    queryKey: knowledgeKeys.versions(selectedPageId),
    queryFn: ({ signal }) => listKnowledgePageVersions(selectedPageId, signal),
    enabled: Boolean(selectedPageId) && panel === "coverage",
  });
  const activeVersionNumber = selectedVersionNumber ?? detailQuery.data?.version_number ?? 0;
  const diffQuery = useQuery({
    queryKey: knowledgeKeys.diff(selectedPageId, activeVersionNumber),
    queryFn: ({ signal }) => getKnowledgePageVersionDiff(selectedPageId, activeVersionNumber, signal),
    enabled: Boolean(selectedPageId) && panel === "coverage" && activeVersionNumber > 0,
  });

  function search(event: FormEvent) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (normalizedQuery === submittedQuery) void pagesQuery.refetch();
    else updateLocation({ query: normalizedQuery, offset: 0, pageId: null, panel: "document", versionNumber: null });
  }

  function selectPage(pageId: string) {
    updateLocation({ query: submittedQuery, pageId, panel: "document", versionNumber: null });
  }

  const result = pagesQuery.isError ? undefined : pagesQuery.data;
  const pages = result?.items ?? [];
  const detail = detailQuery.data;
  const detailError = detailQuery.error instanceof Error ? detailQuery.error.message : "";
  return (
    <section className="knowledge-layout">
      <aside className="knowledge-index">
        <form className="inline-search" onSubmit={search}>
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="检索专题"
            aria-label="检索知识专题"
          />
        </form>
        <div className="knowledge-count">
          {result ? `${result.total} 个专题` : pagesQuery.isError ? "专题总量未知" : "正在统计专题…"}
        </div>
        <div className="knowledge-index-filters">
          <label>
            专题类型
            <select
              aria-label="专题类型"
              value={location.pageType}
              onChange={(event) =>
                updateLocation({
                  pageType: event.target.value,
                  offset: 0,
                  pageId: null,
                  panel: "document",
                  versionNumber: null,
                })
              }
            >
              <option value="">全部类型</option>
              {[
                ...new Set([
                  ...Object.keys(result?.facets.page_type ?? {}),
                  ...(location.pageType ? [location.pageType] : []),
                ]),
              ]
                .sort()
                .map((kind) => (
                  <option key={kind} value={kind}>
                    {knowledgeTypeLabel(kind)}
                  </option>
                ))}
            </select>
          </label>
          <label>
            排序
            <select
              aria-label="知识专题排序"
              value={`${location.sortBy}:${location.sortDirection}`}
              onChange={(event) => {
                const latest = event.target.value === "updated_at:desc";
                updateLocation({
                  sortBy: latest ? "updated_at" : "title",
                  sortDirection: latest ? "desc" : "asc",
                  offset: 0,
                  pageId: null,
                  panel: "document",
                  versionNumber: null,
                });
              }}
            >
              <option value="title:asc">名称 A–Z</option>
              <option value="updated_at:desc">最近更新</option>
            </select>
          </label>
        </div>
        <div className="knowledge-page-list">
          {pagesQuery.isPending ? (
            <Spinner label="正在加载知识专题" />
          ) : pagesQuery.error && !result ? (
            <ErrorState
              message={pagesQuery.error instanceof Error ? pagesQuery.error.message : "知识专题加载失败"}
              retry={() => void pagesQuery.refetch()}
            />
          ) : pages.length ? (
            pages.map((page) => (
              <button
                key={page.id}
                type="button"
                className={selectedPageId === page.id ? "active" : ""}
                onClick={() => selectPage(page.id)}
              >
                <BookOpenText size={17} />
                <span>
                  <strong>{page.title}</strong>
                  <small>
                    {knowledgeTypeLabel(page.page_type)} · {formatDate(page.updated_at)}
                  </small>
                </span>
                <ChevronRight size={16} />
              </button>
            ))
          ) : (
            <EmptyState title="暂无知识专题" />
          )}
        </div>
        {result ? (
          <ResultPagination
            totalRows={result.total}
            offset={location.offset}
            pageSize={KNOWLEDGE_PAGE_SIZE}
            ariaLabel="知识专题分页"
            onPageChange={(offset) => updateLocation({ offset, pageId: null, panel: "document", versionNumber: null })}
          />
        ) : null}
      </aside>
      <article className="knowledge-document">
        {invalidPageId ? (
          <ErrorState message="知识专题链接无效" />
        ) : detailQuery.isFetching ? (
          <Spinner label="正在读取专题版本" />
        ) : detailError ? (
          <ErrorState message={detailError} retry={() => void detailQuery.refetch()} />
        ) : detail ? (
          <>
            <header>
              <div>
                <p className="eyebrow">{knowledgeTypeLabel(detail.page_type)}</p>
                <h2>{detail.title}</h2>
              </div>
            </header>
            <dl className="document-metadata">
              <div>
                <dt>版本</dt>
                <dd>v{detail.version_number}</dd>
              </div>
              <div>
                <dt>证据快照</dt>
                <dd>{formatDate(detail.source_snapshot_at, true)}</dd>
              </div>
            </dl>
            <ResearchTabList
              idPrefix="knowledge"
              ariaLabel="知识专题视图"
              className="view-tabs knowledge-tabs"
              activeTab={panel}
              tabs={[
                {
                  key: "document",
                  label: "专题正文",
                  icon: <BookOpenText size={16} />,
                  panelId: "knowledge-active-panel",
                },
                {
                  key: "coverage",
                  label: "覆盖与版本",
                  icon: <History size={16} />,
                  panelId: "knowledge-active-panel",
                },
              ]}
              onChange={(next) =>
                updateLocation({ query: submittedQuery, pageId: selectedPageId, panel: next, versionNumber: null })
              }
            />
            {panel === "document" ? (
              <div
                className="knowledge-document-panel"
                role="tabpanel"
                id="knowledge-active-panel"
                aria-labelledby="knowledge-tab-document"
              >
                <KnowledgeDocument markdown={detail.rendered_markdown} title={detail.title} />
              </div>
            ) : (
              <div
                className="knowledge-governance"
                role="tabpanel"
                id="knowledge-active-panel"
                aria-labelledby="knowledge-tab-coverage"
              >
                {coverageQuery.isPending ? (
                  <Spinner label="正在计算专题覆盖" />
                ) : coverageQuery.error ? (
                  <ErrorState
                    message={coverageQuery.error instanceof Error ? coverageQuery.error.message : "专题覆盖加载失败"}
                    retry={() => void coverageQuery.refetch()}
                  />
                ) : coverageQuery.data ? (
                  <>
                    <section className="knowledge-coverage-metrics" aria-label="专题覆盖摘要">
                      <div>
                        <strong>{coverageQuery.data.fact_count}</strong>
                        <span>专题要点</span>
                      </div>
                      <div>
                        <strong>{coverageQuery.data.source_count}</strong>
                        <span>独立来源</span>
                      </div>
                      <div>
                        <strong>{coverageQuery.data.linked_entity_count}</strong>
                        <span>关联实体</span>
                      </div>
                      <div>
                        <strong>{coverageQuery.data.uncited_fact_count}</strong>
                        <span>缺少引用</span>
                      </div>
                    </section>
                    <section className="knowledge-predicate-coverage">
                      <header>
                        <div>
                          <ShieldCheck size={17} />
                          <h3>覆盖范围</h3>
                        </div>
                        <span>v{coverageQuery.data.version_number}</span>
                      </header>
                      {coverageQuery.data.predicates.length ? (
                        <ScrollableTableRegion ariaLabel="知识事实覆盖范围">
                          <table aria-label="知识事实覆盖范围">
                            <thead>
                              <tr>
                                <th>关系类型</th>
                                <th>事实数</th>
                                <th>已引用</th>
                              </tr>
                            </thead>
                            <tbody>
                              {coverageQuery.data.predicates.map((item) => (
                                <tr key={item.predicate}>
                                  <td title={item.predicate}>{knowledgePredicateLabel(item.predicate)}</td>
                                  <td>{item.fact_count}</td>
                                  <td>{item.cited_fact_count}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </ScrollableTableRegion>
                      ) : (
                        <EmptyState title="当前版本尚无专题要点" />
                      )}
                    </section>
                  </>
                ) : null}
                <section className="knowledge-history-section">
                  <header>
                    <History size={17} />
                    <h3>版本历史</h3>
                  </header>
                  {versionsQuery.isPending ? (
                    <Spinner label="正在读取版本历史" />
                  ) : versionsQuery.error ? (
                    <ErrorState
                      message={versionsQuery.error instanceof Error ? versionsQuery.error.message : "版本历史加载失败"}
                      retry={() => void versionsQuery.refetch()}
                    />
                  ) : versionsQuery.data?.length ? (
                    <div className="knowledge-history-grid">
                      <ul className="knowledge-version-list" aria-label="专题版本">
                        {versionsQuery.data.map((version) => (
                          <li key={version.version_number}>
                            <button
                              type="button"
                              className={activeVersionNumber === version.version_number ? "active" : ""}
                              aria-current={activeVersionNumber === version.version_number ? "true" : undefined}
                              onClick={() =>
                                updateLocation({
                                  query: submittedQuery,
                                  pageId: selectedPageId,
                                  panel: "coverage",
                                  versionNumber: version.version_number,
                                })
                              }
                            >
                              <span>
                                <strong>v{version.version_number}</strong>
                                {version.is_current ? <small className="knowledge-current-label">当前</small> : null}
                              </span>
                              <small>{formatDate(version.source_snapshot_at, true)}</small>
                              <em>
                                +{version.added_fact_count} / -{version.removed_fact_count} 事实
                              </em>
                            </button>
                          </li>
                        ))}
                      </ul>
                      <div className="knowledge-version-diff" aria-live="polite">
                        {diffQuery.isPending ? (
                          <Spinner label="正在比对版本" />
                        ) : diffQuery.error ? (
                          <ErrorState
                            message={diffQuery.error instanceof Error ? diffQuery.error.message : "版本差异加载失败"}
                            retry={() => void diffQuery.refetch()}
                          />
                        ) : diffQuery.data ? (
                          <>
                            <header>
                              <div>
                                <p className="eyebrow">版本差异</p>
                                <h4>
                                  {diffQuery.data.from_version_number
                                    ? `v${diffQuery.data.from_version_number} → v${diffQuery.data.to_version_number}`
                                    : `初始版本 v${diffQuery.data.to_version_number}`}
                                </h4>
                              </div>
                              <span>
                                +{diffQuery.data.added_fact_count} / -{diffQuery.data.removed_fact_count} 事实
                              </span>
                            </header>
                            {!diffQuery.data.added_fact_count &&
                            !diffQuery.data.removed_fact_count &&
                            !diffQuery.data.added_source_count &&
                            !diffQuery.data.removed_source_count ? (
                              <EmptyState title="与上一版本无内容差异" />
                            ) : (
                              <>
                                <KnowledgeChangeList diff={diffQuery.data} kind="added" />
                                <KnowledgeChangeList diff={diffQuery.data} kind="removed" />
                                {diffQuery.data.truncated ? (
                                  <p className="inline-warning">差异过多，当前仅展示每类前 100 条。</p>
                                ) : null}
                              </>
                            )}
                          </>
                        ) : null}
                      </div>
                    </div>
                  ) : (
                    <EmptyState title="尚无版本历史" />
                  )}
                </section>
              </div>
            )}
          </>
        ) : (
          <EmptyState title="选择一个知识专题" detail="选择后查看可追溯的当前版本" />
        )}
      </article>
    </section>
  );
}
