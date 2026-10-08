import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useMessages } from "../lib/i18n";
import { comparisonMessages } from "../lib/i18n/comparison";
import type { useCollectionCatalog } from "../lib/useCollectionCatalog";

/** Compact directory controls; safe inside the batch picker's existing form. */
export function CollectionDirectoryControls({
  catalog,
  pending = false,
}: {
  catalog: ReturnType<typeof useCollectionCatalog>;
  pending?: boolean;
}) {
  const t = useMessages(comparisonMessages);
  const total = catalog.query.data?.total ?? 0;
  const loading = pending || catalog.query.isFetching;
  return (
    <div className="stack-form">
      <label>
        {t("搜索列表名称或说明")}
        <input
          value={catalog.draft}
          onChange={(event) => catalog.setDraft(event.target.value)}
          disabled={pending}
          maxLength={256}
          placeholder={t("搜索列表")}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              catalog.search();
            }
          }}
        />
      </label>
      <button className="secondary-button" type="button" disabled={loading} onClick={() => catalog.search()}>
        <Search size={16} />
        {t("筛选列表")}
      </button>
      {catalog.query.data ? (
        <nav className="row-actions" aria-label={t("列表目录分页")} style={{ flexWrap: "wrap", fontSize: 12 }}>
          <button
            className="icon-button"
            type="button"
            aria-label={t("列表目录上一页")}
            disabled={loading || !catalog.filter.offset}
            onClick={() => catalog.changePage(Math.max(0, catalog.filter.offset - 25))}
          >
            <ChevronLeft size={16} />
          </button>
          <span>
            {t("第 {page} / {pages} 页 · 共 {count} 条", {
              page: Math.floor(catalog.filter.offset / 25) + 1,
              pages: Math.max(1, Math.ceil(total / 25)),
              count: total,
            })}
          </span>
          <button
            className="icon-button"
            type="button"
            aria-label={t("列表目录下一页")}
            disabled={loading || catalog.filter.offset + 25 >= total}
            onClick={() => catalog.changePage(catalog.filter.offset + 25)}
          >
            <ChevronRight size={16} />
          </button>
        </nav>
      ) : null}
    </div>
  );
}
