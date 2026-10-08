import { useQuery } from "@tanstack/react-query";
import { BookOpenText, History } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import "./knowledge-pagination.css";
import "../styles/knowledge.css";

import { EmptyState, ErrorState, formatDate, Spinner } from "../components/common";
import { ResearchTabList } from "../components/ResearchTabList";
import {
  getKnowledgePage,
  getKnowledgePageCoverage,
  getKnowledgePageVersionDiff,
  knowledgeKeys,
  listKnowledgePageVersions,
  searchKnowledgePages,
} from "../lib/contracts/knowledge";
import { useMessages } from "../lib/i18n";
import { knowledgeMessages } from "../lib/i18n/knowledge";
import { useSelectedRecordFocus } from "../lib/useSelectedRecordFocus";
import type { KnowledgePanel } from "../lib/workspaceRouting";
import { KnowledgeCatalog } from "./knowledge/KnowledgeCatalog";
import { KnowledgeCoverage } from "./knowledge/KnowledgeCoverage";
import { KnowledgeDocument } from "./knowledge/KnowledgeDocument";
import { KnowledgeVersionHistory } from "./knowledge/KnowledgeVersionHistory";
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
  const text = useMessages(knowledgeMessages);
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
    requestFocus(pageId);
    updateLocation({ query: submittedQuery, pageId, panel: "document", versionNumber: null });
  }

  const result = pagesQuery.isError ? undefined : pagesQuery.data;
  const detail = detailQuery.data;
  const detailError = detailQuery.error instanceof Error ? detailQuery.error.message : "";
  const { headingRef, requestFocus } = useSelectedRecordFocus(
    selectedPageId || null,
    Boolean(detail?.id === selectedPageId && !detailQuery.isFetching && !detailQuery.error),
  );
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
          <ErrorState message={text("知识专题链接无效")} />
        ) : detailQuery.isFetching ? (
          <Spinner label={text("正在读取专题版本")} />
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
                <dt>{text("版本")}</dt>
                <dd>v{detail.version_number}</dd>
              </div>
              <div>
                <dt>{text("证据快照")}</dt>
                <dd>{formatDate(detail.source_snapshot_at, true)}</dd>
              </div>
            </dl>
            <ResearchTabList
              idPrefix="knowledge"
              ariaLabel={text("知识专题视图")}
              className="view-tabs knowledge-tabs"
              activeTab={panel}
              tabs={[
                {
                  key: "document",
                  label: text("专题正文"),
                  icon: <BookOpenText size={16} />,
                  panelId: "knowledge-active-panel",
                },
                {
                  key: "coverage",
                  label: text("覆盖与版本"),
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
                <KnowledgeCoverage query={coverageQuery} />
                <KnowledgeVersionHistory
                  versions={versionsQuery}
                  diff={diffQuery}
                  activeVersion={activeVersionNumber}
                  onVersion={(versionNumber) =>
                    updateLocation({ query: submittedQuery, pageId: selectedPageId, panel: "coverage", versionNumber })
                  }
                />
              </div>
            )}
          </>
        ) : (
          <EmptyState title={text("选择一个知识专题")} detail={text("选择后查看可追溯的当前版本")} />
        )}
      </article>
    </section>
  );
}
