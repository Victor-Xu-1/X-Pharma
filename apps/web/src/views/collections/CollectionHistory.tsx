import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorState, formatDate, Spinner } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import { collectionsKeys, listCollectionVersions } from "../../lib/contracts/collections";

export function CollectionHistory({ collectionId, version }: { collectionId: string; version: number }) {
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
      <summary>列表变更历史</summary>
      <p className="muted">仅所有者可见。记录列表设置与成员编号，不是药物事实的历史快照。</p>
      {open ? (
        history.isPending ? (
          <Spinner label="正在读取列表历史" />
        ) : history.error ? (
          <ErrorState
            message={history.error instanceof Error ? history.error.message : "列表历史加载失败"}
            retry={() => void history.refetch()}
          />
        ) : (
          <>
            <ScrollableTableRegion ariaLabel="列表变更历史">
              <table aria-label="列表变更历史">
                <thead>
                  <tr>
                    <th>版本</th>
                    <th>名称与说明</th>
                    <th>共享范围</th>
                    <th>成员数</th>
                    <th>修改时间</th>
                  </tr>
                </thead>
                <tbody>
                  {history.data?.pages
                    .flatMap((page) => page.slice(0, 10))
                    .map((item) => {
                      const snapshot = item.snapshot_json;
                      const name = typeof snapshot.name === "string" ? snapshot.name : "未记录";
                      const description = typeof snapshot.description === "string" ? snapshot.description : "";
                      const members = Array.isArray(snapshot.member_entity_ids)
                        ? snapshot.member_entity_ids.length
                        : "未记录";
                      return (
                        <tr key={item.id}>
                          <td>v{item.version}</td>
                          <td>
                            <strong>{name}</strong>
                            <small className="cell-subtitle">{description || "无说明"}</small>
                          </td>
                          <td>{snapshot.visibility === "tenant" ? "团队共享" : "仅自己可见"}</td>
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
                {history.isFetchingNextPage ? "读取中" : "读取更早版本"}
              </button>
            ) : null}
            {!history.data?.pages[0]?.length ? <p className="muted">暂无历史记录</p> : null}
          </>
        )
      ) : null}
    </details>
  );
}
