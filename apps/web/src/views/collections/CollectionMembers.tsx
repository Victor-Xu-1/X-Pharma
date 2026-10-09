import { useQuery } from "@tanstack/react-query";
import { Columns3, Plus, Search, Trash2, X } from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { CollectionComparisonMatrix } from "../../components/CollectionComparisonMatrix";
import { EmptyState, ErrorState, formatDate, Spinner } from "../../components/common";
import { EntityIdentityLabel } from "../../components/EntityIdentityLabel";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import {
  type CollectionDetail,
  type CollectionEntity,
  collectionsKeys,
  searchCollectionEntities,
} from "../../lib/contracts/collections";
import { entityTypeLabel } from "../../lib/entityPresentation";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { collectionsMessages } from "../../lib/i18n/collections";
import { isPublicEntityIdentifierNamespace } from "../../lib/publicEntity";

const maxCompared = 4;
const helpId = "collection-comparison-selection-help";

export function CollectionMembers({
  detail,
  comparedEntityIds,
  onLocationChange,
  onOpenEntity,
  pending,
  add,
  remove,
}: {
  detail: CollectionDetail;
  comparedEntityIds: string[];
  onLocationChange: (id: string | null, entityIds: string[], replace?: boolean) => void;
  onOpenEntity: (entity: CollectionEntity) => void;
  pending: boolean;
  add: (entity: CollectionEntity) => Promise<boolean>;
  remove: (entity: CollectionEntity) => Promise<boolean>;
}) {
  const text = useMessages(collectionsMessages);
  const number = new Intl.NumberFormat(formattingLocale());
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [optimistic, setOptimistic] = useState<string[] | null>(null);
  const [limitReached, setLimitReached] = useState(false);
  const search = useQuery({
    queryKey: collectionsKeys.search(query),
    queryFn: ({ signal }) => searchCollectionEntities(query, signal),
    enabled: Boolean(query) && detail.editable,
  });
  const memberIds = useMemo(() => new Set(detail.members.map((member) => member.entity.id)), [detail.members]);
  const canonical = useMemo(
    () => comparedEntityIds.filter((id) => memberIds.has(id)).slice(0, maxCompared),
    [comparedEntityIds, memberIds],
  );
  const selectedIds = (optimistic ?? canonical).filter((id) => memberIds.has(id));
  const compared = selectedIds
    .map((id) => detail.members.find((member) => member.entity.id === id)?.entity)
    .filter((entity): entity is CollectionEntity => Boolean(entity));
  useEffect(() => {
    if (
      optimistic &&
      optimistic.length === canonical.length &&
      optimistic.every((id, index) => id === canonical[index])
    )
      setOptimistic(null);
  }, [canonical, optimistic]);
  useEffect(() => {
    if (canonical.length !== comparedEntityIds.length || canonical.some((id, index) => id !== comparedEntityIds[index]))
      onLocationChange(detail.id, canonical, true);
  }, [canonical, comparedEntityIds, detail.id, onLocationChange]);
  function select(id: string, checked: boolean) {
    if (checked && !selectedIds.includes(id) && selectedIds.length >= maxCompared) {
      setLimitReached(true);
      return;
    }
    setLimitReached(false);
    const next = checked ? [...new Set([...selectedIds, id])] : selectedIds.filter((value) => value !== id);
    setOptimistic(next);
    onLocationChange(detail.id, next, true);
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (draft.trim()) setQuery(draft.trim());
  }
  return (
    <>
      {limitReached ? (
        <p className="inline-error" role="alert">
          {text("并排比较最多选择 4 个条目，请先取消一个已选条目")}
        </p>
      ) : null}
      {detail.editable && detail.member_count < 20 ? (
        <form className="query-toolbar compact-form" onSubmit={submit}>
          <div className="query-input">
            <Search size={17} />
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={text("搜索要加入的药物、靶点、机构或适应症")}
              aria-label={text("搜索要加入的药物、靶点、机构或适应症")}
            />
          </div>
          <button className="secondary-button" type="submit" disabled={search.isFetching || !draft.trim()}>
            {search.isFetching ? text("检索中") : text("检索")}
          </button>
        </form>
      ) : null}
      {detail.editable && query ? (
        search.isPending ? (
          <Spinner label={text("正在搜索可加入的条目")} />
        ) : search.error ? (
          <ErrorState
            message={search.error instanceof Error ? search.error.message : text("条目检索失败")}
            retry={() => void search.refetch()}
          />
        ) : search.data?.items.length ? (
          <div className="entity-add-strip">
            {search.data.items.map((entity) => (
              <button
                type="button"
                key={entity.id}
                aria-label={text("加入 {name}", { name: entity.name })}
                disabled={memberIds.has(entity.id) || pending || detail.member_count >= 20}
                onClick={() => void add(entity)}
              >
                <Plus size={14} />
                <span>
                  <strong>{entity.name}</strong>
                  <small>{entityTypeLabel(entity)}</small>
                </span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title={text("未找到可加入的条目")} detail={text("尝试名称、别名或公共资料编号")} />
        )
      ) : null}
      {detail.members.length ? (
        <>
          <div className="comparison-selection-toolbar">
            <div className="comparison-selection-copy">
              <span aria-live="polite" aria-atomic="true">
                <Columns3 size={16} aria-hidden="true" />
                {text("并排比较")}{" "}
                <strong>
                  {number.format(selectedIds.length)}/{maxCompared}
                </strong>
              </span>
              <small id={helpId}>
                {selectedIds.length >= maxCompared
                  ? text("已达到上限，请先取消一个已选条目")
                  : text("选择 2 至 4 个条目生成对比表")}
              </small>
            </div>
            <button
              type="button"
              className="icon-button"
              title={text("清空比较")}
              aria-label={text("清空比较")}
              disabled={!selectedIds.length}
              onClick={() => {
                setOptimistic([]);
                onLocationChange(detail.id, [], true);
              }}
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
          <ScrollableTableRegion ariaLabel={text("对比列表内容")} className="comparison-table">
            <table aria-label={text("对比列表内容")}>
              <thead>
                <tr>
                  <th scope="col">{text("比较")}</th>
                  <th scope="col">#</th>
                  <th scope="col">{text("名称")}</th>
                  <th scope="col">{text("类型")}</th>
                  <th scope="col">{text("资料编号")}</th>
                  <th scope="col">{text("更新时间")}</th>
                  <th scope="col" aria-label={text("操作")} />
                </tr>
              </thead>
              <tbody>
                {detail.members.map((member, index) => {
                  const checked = selectedIds.includes(member.entity.id);
                  const identifiers = Object.entries(member.entity.external_ids)
                    .filter(([namespace]) => isPublicEntityIdentifierNamespace(namespace))
                    .map(([namespace, value]) => `${namespace.toUpperCase()}: ${value}`)
                    .join(" · ");
                  return (
                    <tr key={member.id} className={checked ? "comparison-member-selected" : undefined}>
                      <td>
                        <input
                          type="checkbox"
                          checked={checked}
                          aria-label={text("纳入情报对比：{name}", { name: member.entity.name })}
                          aria-describedby={helpId}
                          onChange={(event) => select(member.entity.id, event.target.checked)}
                        />
                      </td>
                      <td>{number.format(index + 1)}</td>
                      <td>
                        <button
                          className="collection-entity-link"
                          type="button"
                          onClick={() => onOpenEntity(member.entity)}
                        >
                          <strong>{member.entity.name}</strong>
                          <small>{member.entity.description}</small>
                        </button>
                      </td>
                      <td>
                        <EntityIdentityLabel entity={member.entity} />
                      </td>
                      <td>{identifiers || text("未记录公共编号")}</td>
                      <td>{formatDate(member.entity.updated_at)}</td>
                      <td>
                        {detail.editable ? (
                          <button
                            className="icon-button"
                            type="button"
                            title={text("移出列表")}
                            aria-label={text("移出 {name}", { name: member.entity.name })}
                            disabled={pending}
                            onClick={() => void remove(member.entity)}
                          >
                            <Trash2 size={16} />
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollableTableRegion>
          <section className="collection-comparison-panel" aria-labelledby="collection-comparison-heading">
            <header>
              <span>
                <strong id="collection-comparison-heading">{text("研发情报对比")}</strong>
                <small>{text("根据当前可查看的信息实时生成")}</small>
              </span>
            </header>
            <CollectionComparisonMatrix entities={compared} onOpenEntity={onOpenEntity} />
          </section>
        </>
      ) : (
        <EmptyState title={text("列表为空")} detail={text("搜索药物、靶点、机构或适应症并加入列表")} />
      )}
    </>
  );
}
