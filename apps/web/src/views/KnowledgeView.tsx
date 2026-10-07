import { useQuery } from "@tanstack/react-query";
import { BookOpenText, History, ShieldCheck } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import "./knowledge-pagination.css";
import "../styles/knowledge.css";

import { EmptyState, ErrorState, formatDate, Spinner } from "../components/common";
import { ResearchTabList } from "../components/ResearchTabList";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import {
  getKnowledgePage,
  getKnowledgePageCoverage,
  getKnowledgePageVersionDiff,
  knowledgeKeys,
  listKnowledgePageVersions,
  searchKnowledgePages,
} from "../lib/contracts/knowledge";
import type { KnowledgePanel } from "../lib/workspaceRouting";
import { KnowledgeCatalog } from "./knowledge/KnowledgeCatalog";
import { KnowledgeChangeList } from "./knowledge/KnowledgeChangeList";
import { KnowledgeDocument } from "./knowledge/KnowledgeDocument";
import { knowledgePredicateLabel } from "./knowledge/knowledgeReading";
import { type KnowledgeLocation, knowledgeTypeLabel } from "./knowledge/knowledgeTypes";

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
  const headingRef = useRef<HTMLHeadingElement>(null);
  const pendingFocus = useRef<string | null>(null);
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
    pendingFocus.current = pageId;
    if (detail?.id === pageId && !detailQuery.isFetching) {
      headingRef.current?.focus();
      pendingFocus.current = null;
    }
    updateLocation({ query: submittedQuery, pageId, panel: "document", versionNumber: null });
  }

  const result = pagesQuery.isError ? undefined : pagesQuery.data;
  const detail = detailQuery.data;
  const detailError = detailQuery.error instanceof Error ? detailQuery.error.message : "";
  useEffect(() => {
    if (
      pendingFocus.current === selectedPageId &&
      detail?.id === selectedPageId &&
      !detailQuery.isFetching &&
      !detailError
    ) {
      headingRef.current?.focus();
      pendingFocus.current = null;
    }
  }, [selectedPageId, detail?.id, detailQuery.isFetching, detailError]);
  return (
    <section className="knowledge-layout">
      <KnowledgeCatalog
        query={query}
        location={location}
        result={result}
        pending={pagesQuery.isPending}
        error={pagesQuery.error}
        onQueryChange={setQuery}
        onSearch={search}
        onRetry={() => void pagesQuery.refetch()}
        onSelect={selectPage}
        onLocationChange={updateLocation}
      />
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
                <h2 ref={headingRef} tabIndex={-1}>
                  {detail.title}
                </h2>
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
