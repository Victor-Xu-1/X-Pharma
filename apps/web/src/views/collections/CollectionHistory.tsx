import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorState, formatDate, Spinner } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import { collectionsKeys, listCollectionVersions } from "../../lib/contracts/collections";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { collectionsMessages } from "../../lib/i18n/collections";

export function CollectionHistory({ collectionId, version }: { collectionId: string; version: number }) {
  const text = useMessages(collectionsMessages);
  const number = new Intl.NumberFormat(formattingLocale());
  const [open, setOpen] = useState(false);
  const history = useInfiniteQuery({
    queryKey: [...collectionsKeys.versions(collectionId), version],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam, signal }) => listCollectionVersions(collectionId, pageParam, signal),
    getNextPageParam: (lastPage) => (lastPage.length > 10 ? lastPage[9]?.version : undefined),
    enabled: open,
  });
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>{text("列表变更历史")}</summary>
      <p className="muted">{text("仅所有者可见。记录列表设置与成员编号，不是药物事实的历史快照。")}</p>
      {open ? (
        history.isPending ? (
          <Spinner label={text("正在读取列表历史")} />
        ) : history.error ? (
          <ErrorState
            message={history.error instanceof Error ? history.error.message : text("列表历史加载失败")}
            retry={() => void history.refetch()}
          />
        ) : (
          <>
            <ScrollableTableRegion ariaLabel={text("列表变更历史")}>
              <table aria-label={text("列表变更历史")}>
                <thead>
                  <tr>
                    <th>{text("版本")}</th>
                    <th>{text("名称与说明")}</th>
                    <th>{text("共享范围")}</th>
                    <th>{text("成员数")}</th>
                    <th>{text("修改时间")}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.data?.pages
                    .flatMap((page) => page.slice(0, 10))
                    .map((item) => {
                      const snapshot = item.snapshot_json;
                      const name = typeof snapshot.name === "string" ? snapshot.name : text("未记录");
                      const description = typeof snapshot.description === "string" ? snapshot.description : "";
                      const members = Array.isArray(snapshot.member_entity_ids)
                        ? number.format(snapshot.member_entity_ids.length)
                        : text("未记录");
                      return (
                        <tr key={item.id}>
                          <td>v{item.version}</td>
                          <td>
                            <strong>{name}</strong>
                            <small className="cell-subtitle">{description || text("无说明")}</small>
                          </td>
                          <td>
                            {snapshot.visibility === "tenant"
                              ? text("团队共享")
                              : snapshot.visibility === "private"
                                ? text("仅自己可见")
                                : typeof snapshot.visibility === "string"
                                  ? snapshot.visibility
                                  : text("未记录")}
                          </td>
                          <td>{members}</td>
                          <td>{formatDate(item.created_at, true)}</td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </ScrollableTableRegion>
            {history.hasNextPage ? (
              <button
                type="button"
                className="secondary-button"
                disabled={history.isFetchingNextPage}
                onClick={() => void history.fetchNextPage()}
              >
                {history.isFetchingNextPage ? text("读取中") : text("读取更早版本")}
              </button>
            ) : null}
            {!history.data?.pages[0]?.length ? <p className="muted">{text("暂无历史记录")}</p> : null}
          </>
        )
      ) : null}
    </details>
  );
}
