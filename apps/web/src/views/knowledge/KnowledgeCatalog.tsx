import { BookOpenText, ChevronRight, Search } from "lucide-react";
import type { FormEvent } from "react";
import { EmptyState, ErrorState, formatDate, Spinner } from "../../components/common";
import { ResponsiveDirectory } from "../../components/ResponsiveDirectory";
import { ResultPagination } from "../../components/ResultPagination";
import { KNOWLEDGE_PAGE_SIZE, type KnowledgeSearchResult } from "../../lib/contracts/knowledge";
import { type KnowledgeLocation, knowledgeTypeLabel } from "./knowledgeTypes";

/** Catalogue visibility is local presentation state; the parent remains the sole query/URL authority. */
export function KnowledgeCatalog({
  query,
  location,
  result,
  pending,
  error,
  onQueryChange,
  onSearch,
  onRetry,
  onSelect,
  onLocationChange,
}: {
  query: string;
  location: KnowledgeLocation;
  result: KnowledgeSearchResult | undefined;
  pending: boolean;
  error: unknown;
  onQueryChange: (query: string) => void;
  onSearch: (event: FormEvent) => void;
  onRetry: () => void;
  onSelect: (pageId: string) => void;
  onLocationChange: (next: Partial<KnowledgeLocation>) => void;
}) {
  const pages = result?.items ?? [];

  function changeFilters(next: Partial<KnowledgeLocation>) {
    onLocationChange({ ...next, offset: 0, pageId: null, panel: "document", versionNumber: null });
  }

  return (
    <ResponsiveDirectory
      selectedKey={location.pageId}
      title="专题目录"
      summary={result ? `${result.total} 个专题` : "检索与筛选"}
      icon={<BookOpenText size={18} aria-hidden="true" />}
      className="knowledge-index"
      contentClassName="knowledge-index-content"
    >
      {(collapse) => (
        <>
          <form className="inline-search" onSubmit={onSearch}>
            <Search size={16} aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="检索专题"
              aria-label="检索知识专题"
            />
          </form>
          <div className="knowledge-count">
            {result ? `${result.total} 个专题` : error ? "专题总量未知" : "正在统计专题…"}
          </div>
          <div className="knowledge-index-filters">
            <label>
              专题类型
              <select
                aria-label="专题类型"
                value={location.pageType}
                onChange={(event) => changeFilters({ pageType: event.target.value })}
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
                  changeFilters({ sortBy: latest ? "updated_at" : "title", sortDirection: latest ? "desc" : "asc" });
                }}
              >
                <option value="title:asc">名称 A–Z</option>
                <option value="updated_at:desc">最近更新</option>
              </select>
            </label>
          </div>
          <div className="knowledge-page-list">
            {pending ? (
              <Spinner label="正在加载知识专题" />
            ) : error && !result ? (
              <ErrorState message={error instanceof Error ? error.message : "知识专题加载失败"} retry={onRetry} />
            ) : pages.length ? (
              pages.map((page) => (
                <button
                  key={page.id}
                  type="button"
                  className={location.pageId === page.id ? "active" : ""}
                  aria-current={location.pageId === page.id ? "true" : undefined}
                  onClick={() => {
                    collapse();
                    onSelect(page.id);
                  }}
                >
                  <BookOpenText size={17} aria-hidden="true" />
                  <span>
                    <strong>{page.title}</strong>
                    <small>
                      {knowledgeTypeLabel(page.page_type)} · {formatDate(page.updated_at)}
                    </small>
                  </span>
                  <ChevronRight size={16} aria-hidden="true" />
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
              onPageChange={(offset) =>
                onLocationChange({ offset, pageId: null, panel: "document", versionNumber: null })
              }
            />
          ) : null}
        </>
      )}
    </ResponsiveDirectory>
  );
}
