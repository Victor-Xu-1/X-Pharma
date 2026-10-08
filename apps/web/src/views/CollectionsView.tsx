import { useQuery } from "@tanstack/react-query";
import { Pencil, RefreshCw, Share2 } from "lucide-react";
import { type RefObject, useEffect, useState } from "react";
import { EmptyState, ErrorState, formatDate, Spinner } from "../components/common";
import { ResearchMetadataDialog } from "../components/ResearchMetadataDialog";
import { ApiError } from "../lib/api";
import {
  addComparisonSetMember,
  type CollectionDetail,
  type CollectionEntity,
  collectionsKeys,
  createComparisonSet,
  getComparisonSet,
  removeComparisonSetMember,
  updateComparisonSet,
} from "../lib/contracts/collections";
import { useCollectionCatalog } from "../lib/useCollectionCatalog";
import { useSelectedRecordFocus } from "../lib/useSelectedRecordFocus";
import { CollectionCatalog } from "./collections/CollectionCatalog";
import { CollectionExport } from "./collections/CollectionExport";
import { CollectionHistory } from "./collections/CollectionHistory";
import { CollectionMembers } from "./collections/CollectionMembers";
import { useCollectionWrites } from "./collections/useCollectionWrites";

type Navigation = (id: string | null, entityIds: string[], replace?: boolean) => void;

export function CollectionsView({
  activeCollectionId,
  comparedEntityIds,
  onLocationChange,
  onOpenEntity,
}: {
  activeCollectionId: string | null;
  comparedEntityIds: string[];
  onLocationChange: Navigation;
  onOpenEntity: (entity: CollectionEntity) => void;
}) {
  const catalog = useCollectionCatalog();
  const activeId = activeCollectionId ?? catalog.query.data?.items[0]?.id ?? "";
  const detailQuery = useQuery({
    queryKey: collectionsKeys.detail(activeId),
    queryFn: ({ signal }) => getComparisonSet(activeId, signal),
    enabled: Boolean(activeId),
  });
  const selected = detailQuery.data;
  const accessDenied = detailQuery.error instanceof ApiError && [401, 403, 404].includes(detailQuery.error.status);
  const { headingRef, requestFocus } = useSelectedRecordFocus(
    activeId || null,
    Boolean(selected?.id === activeId && !detailQuery.isFetching && !detailQuery.error),
  );
  const navigate: Navigation = (id, entityIds, replace) => {
    if (id && !replace) requestFocus(id);
    onLocationChange(id, entityIds, replace);
  };
  const writes = useCollectionWrites(activeId, navigate);
  useEffect(() => {
    if (!activeCollectionId && activeId) onLocationChange(activeId, [], true);
  }, [activeCollectionId, activeId, onLocationChange]);
  return (
    <section className="data-section collections-section">
      {writes.error ? (
        <p className="inline-error" role="alert">
          {writes.error}
        </p>
      ) : null}
      {writes.notice ? (
        <p className="inline-feedback" role="status">
          {writes.notice}
        </p>
      ) : null}
      <div className="collections-layout">
        <CollectionCatalog
          catalog={catalog}
          activeId={activeId}
          pending={writes.pending}
          onSelect={(id) => navigate(id, [], false)}
          onCreate={(name, visibility) =>
            writes.write(() => createComparisonSet({ name, visibility }), "对比列表已创建", true)
          }
        />
        <div className="collections-main">
          {activeId && detailQuery.isPending ? (
            <Spinner label="正在加载对比与列表" />
          ) : detailQuery.error && (!selected || accessDenied) ? (
            <ErrorState
              message={detailQuery.error instanceof Error ? detailQuery.error.message : "列表不存在或无权访问"}
              retry={() => void detailQuery.refetch()}
            />
          ) : selected ? (
            <>
              {detailQuery.error ? (
                <ErrorState
                  message="刷新失败，以下为上次读取的列表；请恢复连接后核对当前版本。"
                  retry={() => void detailQuery.refetch()}
                />
              ) : null}
              <CollectionContent
                key={selected.id}
                detail={selected}
                comparedEntityIds={comparedEntityIds}
                onLocationChange={navigate}
                onOpenEntity={onOpenEntity}
                writes={writes}
                refreshing={detailQuery.isFetching}
                stale={detailQuery.isError}
                refresh={() => void detailQuery.refetch()}
                headingRef={headingRef}
              />
            </>
          ) : (
            <EmptyState
              title="建立你的研究列表"
              detail="先创建列表，再从情报检索或对象档案加入关注对象；可进行对比、保存证据并共享给团队。"
            />
          )}
        </div>
      </div>
    </section>
  );
}

function CollectionContent({
  detail,
  comparedEntityIds,
  onLocationChange,
  onOpenEntity,
  writes,
  refreshing,
  stale,
  refresh,
  headingRef,
}: {
  detail: CollectionDetail;
  comparedEntityIds: string[];
  onLocationChange: Navigation;
  onOpenEntity: (entity: CollectionEntity) => void;
  writes: ReturnType<typeof useCollectionWrites>;
  refreshing: boolean;
  stale: boolean;
  refresh: () => void;
  headingRef: RefObject<HTMLHeadingElement | null>;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  function openEditor() {
    setName(detail.name);
    setDescription(detail.description);
    setEditing(true);
  }
  return (
    <>
      <div className="section-toolbar collection-heading" style={{ flexWrap: "wrap" }}>
        <span style={{ flex: "1 1 180px", minWidth: 0 }}>
          <h2 ref={headingRef} tabIndex={-1}>
            {detail.name}
          </h2>
          <small>{detail.description || `更新于 ${formatDate(detail.updated_at)}`}</small>
        </span>
        <div className="row-actions">
          <button
            className="icon-button"
            type="button"
            aria-label="刷新当前列表"
            title="刷新当前列表"
            disabled={refreshing || writes.pending}
            onClick={refresh}
          >
            <RefreshCw size={16} />
          </button>
          {detail.editable ? (
            <>
              <button className="secondary-button" type="button" disabled={writes.pending} onClick={openEditor}>
                <Pencil size={16} />
                编辑列表
              </button>
              <button
                className="secondary-button"
                type="button"
                disabled={writes.pending}
                onClick={() =>
                  void writes.write(
                    () =>
                      updateComparisonSet(detail.id, {
                        expected_version: detail.version,
                        visibility: detail.visibility === "tenant" ? "private" : "tenant",
                      }),
                    "共享范围已更新",
                  )
                }
              >
                <Share2 size={16} />
                {detail.visibility === "tenant" ? "设为私有" : "团队共享"}
              </button>
            </>
          ) : (
            <small>共享列表 · 只读</small>
          )}
          <CollectionExport detail={detail} changing={writes.pending} refreshing={refreshing} stale={stale} />
        </div>
      </div>
      <CollectionMembers
        detail={detail}
        comparedEntityIds={comparedEntityIds}
        onLocationChange={onLocationChange}
        onOpenEntity={onOpenEntity}
        pending={writes.pending}
        add={(entity) =>
          writes.write(
            () => addComparisonSetMember(detail.id, { entity_id: entity.id, expected_version: detail.version }),
            `${entity.name} 已加入对比`,
          )
        }
        remove={(entity) =>
          writes.write(
            () => removeComparisonSetMember(detail.id, entity.id, { expected_version: detail.version }),
            "条目已移出列表",
          )
        }
      />
      {detail.editable ? <CollectionHistory collectionId={detail.id} version={detail.version} /> : null}
      <ResearchMetadataDialog
        title="编辑对比列表"
        open={editing}
        name={name}
        description={description}
        pending={writes.pending}
        error={writes.error}
        onNameChange={setName}
        onDescriptionChange={setDescription}
        onClose={() => {
          if (!writes.pending) setEditing(false);
        }}
        onSubmit={(event) => {
          event.preventDefault();
          void writes
            .write(
              () =>
                updateComparisonSet(detail.id, {
                  expected_version: detail.version,
                  name: name.trim(),
                  description: description.trim(),
                }),
              "列表名称与说明已保存",
            )
            .then((saved) => {
              if (saved) setEditing(false);
            });
        }}
      />
    </>
  );
}
