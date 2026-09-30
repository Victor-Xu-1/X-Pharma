import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Columns3, Download, Plus, Search, Share2, Trash2, X } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { CollectionComparisonMatrix } from "../components/CollectionComparisonMatrix";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../components/common";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import {
  addComparisonSetMember,
  type CollectionDetail,
  type CollectionEntity,
  type CollectionSummary,
  collectionsKeys,
  createComparisonSet,
  exportComparisonSet,
  getComparisonSet,
  getWorkspaceExportPolicy,
  listComparisonSets,
  removeComparisonSetMember,
  searchCollectionEntities,
  updateComparisonSet,
} from "../lib/contracts/collections";
import { downloadBlob, type ExportFormat } from "../lib/download";

const comparisonFieldLabels: Record<string, string> = {
  position: "序号",
  id: "记录编号",
  entity_type: "类型",
  name: "名称",
  description: "描述",
  external_ids: "外部标识",
  created_at: "创建时间",
  updated_at: "更新时间",
};
const fieldLabels: Record<string, string> = comparisonFieldLabels;
const requiredFields = new Set(["id", "entity_type", "name"]);
const maxComparedEntities = 4;
const comparisonSelectionHelpId = "collection-comparison-selection-help";
const entityTypeLabels: Record<CollectionEntity["entity_type"], string> = {
  target: "靶点",
  drug: "药物",
  organization: "研发机构",
  disease: "适应症",
  clinical_trial: "临床试验",
  patent: "专利",
  transaction: "交易",
  product: "产品",
  technology: "技术",
  person: "人员",
};

export function CollectionsView({
  activeCollectionId,
  comparedEntityIds,
  onLocationChange,
  onOpenEntity,
}: {
  activeCollectionId: string | null;
  comparedEntityIds: string[];
  onLocationChange: (collectionId: string | null, entityIds: string[], replace?: boolean) => void;
  onOpenEntity: (entity: CollectionEntity) => void;
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [exportFormat, setExportFormat] = useState<ExportFormat>("xlsx");
  const [exportFields, setExportFields] = useState<string[]>(["position", "id", "entity_type", "name"]);
  const [optimisticComparedEntityIds, setOptimisticComparedEntityIds] = useState<string[] | null>(null);

  const setsQuery = useQuery({
    queryKey: collectionsKeys.sets,
    queryFn: ({ signal }) => listComparisonSets(signal),
  });
  const policyQuery = useQuery({
    queryKey: collectionsKeys.policy,
    queryFn: ({ signal }) => getWorkspaceExportPolicy(signal),
  });
  const sets = setsQuery.data ?? [];
  const activeId = sets.some((item) => item.id === activeCollectionId)
    ? (activeCollectionId ?? "")
    : (sets[0]?.id ?? "");
  const detailQuery = useQuery({
    queryKey: collectionsKeys.detail(activeId),
    queryFn: ({ signal }) => getComparisonSet(activeId, signal),
    enabled: Boolean(activeId),
  });
  const entitySearch = useQuery({
    queryKey: collectionsKeys.search(submittedQuery),
    queryFn: ({ signal }) => searchCollectionEntities(submittedQuery, signal),
    enabled: Boolean(submittedQuery),
  });
  const selected = detailQuery.data ?? null;
  const policy = policyQuery.data ?? null;
  const comparisonAllowedFields =
    policy?.allowed_fields.filter((field) => !field.includes(".") && field !== "review_status") ?? [];
  const searchResults = entitySearch.data?.items ?? [];

  useEffect(() => {
    if (!setsQuery.data) return;
    const canonicalCollectionId = activeId || null;
    if (canonicalCollectionId !== activeCollectionId) {
      onLocationChange(canonicalCollectionId, [], true);
    }
  }, [activeCollectionId, activeId, onLocationChange, setsQuery.data]);

  useEffect(() => {
    if (!policyQuery.data) return;
    const nextPolicy = policyQuery.data;
    setExportFormat(nextPolicy.allowed_formats[0] ?? "xlsx");
    setExportFields(nextPolicy.allowed_fields.filter((field) => requiredFields.has(field) || field === "position"));
  }, [policyQuery.data]);

  const commitDetail = useCallback(
    (detail: CollectionDetail, prepend = false) => {
      queryClient.setQueryData(collectionsKeys.detail(detail.id), detail);
      queryClient.setQueryData<CollectionSummary[]>(collectionsKeys.sets, (current = []) => {
        const summary = detail satisfies CollectionSummary;
        if (prepend && !current.some((item) => item.id === detail.id)) return [summary, ...current];
        return current.map((item) => (item.id === detail.id ? summary : item));
      });
      const memberIds = new Set(detail.members.map((member) => member.entity.id));
      onLocationChange(
        detail.id,
        prepend ? [] : comparedEntityIds.filter((entityId) => memberIds.has(entityId)).slice(0, maxComparedEntities),
      );
    },
    [comparedEntityIds, onLocationChange, queryClient],
  );

  const createMutation = useMutation({
    mutationFn: ({ nextName, visibility }: { nextName: string; visibility: "private" | "tenant" }) =>
      createComparisonSet({ name: nextName, visibility }),
  });
  const addMutation = useMutation({
    mutationFn: ({ entity, detail }: { entity: CollectionEntity; detail: CollectionDetail }) =>
      addComparisonSetMember(detail.id, { entity_id: entity.id, expected_version: detail.version }),
  });
  const removeMutation = useMutation({
    mutationFn: ({ entity, detail }: { entity: CollectionEntity; detail: CollectionDetail }) =>
      removeComparisonSetMember(detail.id, entity.id, { expected_version: detail.version }),
  });
  const visibilityMutation = useMutation({
    mutationFn: (detail: CollectionDetail) =>
      updateComparisonSet(detail.id, {
        expected_version: detail.version,
        visibility: detail.visibility === "tenant" ? "private" : "tenant",
      }),
  });
  const exportMutation = useMutation({
    mutationFn: ({ detail, format, fields }: { detail: CollectionDetail; format: ExportFormat; fields: string[] }) =>
      exportComparisonSet(detail.id, {
        expected_version: detail.version,
        export_format: format,
        fields,
        idempotency_key: crypto.randomUUID(),
      }),
  });
  const changingSet =
    createMutation.isPending || addMutation.isPending || removeMutation.isPending || visibilityMutation.isPending;

  async function createSet(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const created = await createMutation.mutateAsync({
        nextName: name.trim(),
        visibility: shared ? "tenant" : "private",
      });
      commitDetail(created, true);
      setName("");
      setNotice("对比列表已创建");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "创建失败");
    }
  }

  async function searchEntities(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setError("");
    setSubmittedQuery(query.trim());
  }

  async function addEntity(entity: CollectionEntity) {
    if (!selected) return;
    setError("");
    try {
      const detail = await addMutation.mutateAsync({ entity, detail: selected });
      commitDetail(detail);
      setNotice(`${entity.name} 已加入对比`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "添加条目失败");
    }
  }

  async function removeEntity(entity: CollectionEntity) {
    if (!selected) return;
    setError("");
    try {
      const detail = await removeMutation.mutateAsync({ entity, detail: selected });
      commitDetail(detail);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "移除条目失败");
    }
  }

  async function updateVisibility() {
    if (!selected?.editable) return;
    setError("");
    try {
      const detail = await visibilityMutation.mutateAsync(selected);
      commitDetail(detail);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "共享范围更新失败");
    }
  }

  async function exportSet() {
    if (!selected || !policy) return;
    setError("");
    try {
      const blob = await exportMutation.mutateAsync({ detail: selected, format: exportFormat, fields: exportFields });
      downloadBlob(blob, `comparison-${selected.id}-v${selected.version}.${exportFormat}`);
      setNotice("导出文件已生成");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "导出失败");
    }
  }

  const existingIds = useMemo(() => new Set(selected?.members.map((item) => item.entity.id) ?? []), [selected]);
  const canonicalComparedIds = useMemo(
    () => comparedEntityIds.filter((entityId) => existingIds.has(entityId)).slice(0, maxComparedEntities),
    [comparedEntityIds, existingIds],
  );
  const renderedComparedIds = optimisticComparedEntityIds ?? canonicalComparedIds;
  const comparedEntities = useMemo(() => {
    if (!selected) return [];
    const entitiesById = new Map(selected.members.map((member) => [member.entity.id, member.entity]));
    return renderedComparedIds
      .map((entityId) => entitiesById.get(entityId))
      .filter((entity): entity is CollectionEntity => Boolean(entity));
  }, [renderedComparedIds, selected]);

  useEffect(() => {
    if (!optimisticComparedEntityIds) return;
    const routeCaughtUp =
      optimisticComparedEntityIds.length === canonicalComparedIds.length &&
      optimisticComparedEntityIds.every((entityId, index) => entityId === canonicalComparedIds[index]);
    if (routeCaughtUp) setOptimisticComparedEntityIds(null);
  }, [canonicalComparedIds, optimisticComparedEntityIds]);

  useEffect(() => {
    if (!selected || selected.id !== activeId) return;
    if (
      canonicalComparedIds.length !== comparedEntityIds.length ||
      canonicalComparedIds.some((entityId, index) => entityId !== comparedEntityIds[index])
    ) {
      onLocationChange(activeId, canonicalComparedIds, true);
    }
  }, [activeId, canonicalComparedIds, comparedEntityIds, onLocationChange, selected]);

  function setEntityCompared(entityId: string, compared: boolean) {
    if (!activeId || !existingIds.has(entityId)) return;
    const currentComparedIds = renderedComparedIds;
    const nextIds = compared
      ? [...currentComparedIds, entityId]
          .filter((value, index, values) => values.indexOf(value) === index)
          .slice(0, maxComparedEntities)
      : currentComparedIds.filter((value) => value !== entityId);
    if (compared && !currentComparedIds.includes(entityId) && currentComparedIds.length >= maxComparedEntities) {
      setError(`并排比较最多选择 ${maxComparedEntities} 个条目，请先取消一个已选条目`);
      return;
    }
    setError("");
    setOptimisticComparedEntityIds(nextIds);
    onLocationChange(activeId, nextIds, true);
  }

  const queryError = setsQuery.error ?? policyQuery.error ?? detailQuery.error ?? entitySearch.error;
  const visibleError =
    error || (queryError instanceof Error ? queryError.message : queryError ? "对比工作区加载失败" : "");
  const loading = setsQuery.isPending || policyQuery.isPending || (Boolean(activeId) && detailQuery.isPending);

  if (loading) return <Spinner label="正在加载对比与列表" />;
  if (visibleError && !setsQuery.data) {
    return (
      <ErrorState
        message={visibleError}
        retry={() => {
          setError("");
          void setsQuery.refetch();
          void policyQuery.refetch();
        }}
      />
    );
  }

  return (
    <section className="data-section collections-section">
      {visibleError ? (
        <p className="inline-error" role="alert">
          {visibleError}
        </p>
      ) : null}
      {notice ? (
        <p className="inline-feedback" role="status">
          {notice}
        </p>
      ) : null}
      <div className="collections-layout">
        <aside className="collections-list" aria-label="对比列表">
          <form className="stack-form" onSubmit={(event) => void createSet(event)}>
            <label>
              新建列表
              <input value={name} onChange={(event) => setName(event.target.value)} maxLength={200} required />
            </label>
            <label className="check-control">
              <input type="checkbox" checked={shared} onChange={(event) => setShared(event.target.checked)} />
              团队共享
            </label>
            <button className="primary-button" type="submit" disabled={!name.trim() || changingSet}>
              <Plus size={16} />
              创建
            </button>
          </form>
          <div className="collection-picker">
            {sets.map((item) => (
              <button
                type="button"
                className={activeId === item.id ? "active" : ""}
                key={item.id}
                onClick={() => onLocationChange(item.id, [], false)}
              >
                <span>
                  <strong>{item.name}</strong>
                  <small>{item.member_count}/20 条</small>
                </span>
                <StatusBadge value={item.visibility === "tenant" ? "团队共享" : "仅自己可见"} />
              </button>
            ))}
          </div>
        </aside>

        <div className="collections-main">
          {!selected ? (
            <EmptyState title="暂无对比列表" detail="创建列表后可加入靶点、药物、公司、试验和专利等条目" />
          ) : (
            <>
              <div className="section-toolbar collection-heading">
                <span>
                  <strong>{selected.name}</strong>
                  <small>{selected.description || `更新于 ${formatDate(selected.updated_at)}`}</small>
                </span>
                {selected.editable ? (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={changingSet}
                    onClick={() => void updateVisibility()}
                  >
                    <Share2 size={16} />
                    {selected.visibility === "tenant" ? "设为私有" : "团队共享"}
                  </button>
                ) : null}
              </div>
              {selected.editable && selected.member_count < 20 ? (
                <form className="query-toolbar compact-form" onSubmit={(event) => void searchEntities(event)}>
                  <div className="query-input">
                    <Search size={17} />
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="搜索要加入的药物、靶点、机构或适应症"
                      aria-label="搜索要加入的药物、靶点、机构或适应症"
                    />
                  </div>
                  <button
                    className="secondary-button"
                    type="submit"
                    disabled={entitySearch.isFetching || !query.trim()}
                  >
                    {entitySearch.isFetching ? "检索中" : "检索"}
                  </button>
                </form>
              ) : null}
              {searchResults.length ? (
                <div className="entity-add-strip">
                  {searchResults.map((entity) => (
                    <button
                      type="button"
                      key={entity.id}
                      aria-label={`加入 ${entity.name}`}
                      disabled={existingIds.has(entity.id) || changingSet}
                      onClick={() => void addEntity(entity)}
                    >
                      <Plus size={14} />
                      <span>
                        <strong>{entity.name}</strong>
                        <small>{entityTypeLabels[entity.entity_type]}</small>
                      </span>
                    </button>
                  ))}
                </div>
              ) : null}
              {selected.members.length ? (
                <>
                  <div className="comparison-selection-toolbar">
                    <div className="comparison-selection-copy">
                      <span aria-live="polite" aria-atomic="true">
                        <Columns3 size={16} aria-hidden="true" />
                        并排比较{" "}
                        <strong>
                          {renderedComparedIds.length}/{maxComparedEntities}
                        </strong>
                      </span>
                      <small id={comparisonSelectionHelpId}>
                        {renderedComparedIds.length >= maxComparedEntities
                          ? "已达到上限，请先取消一个已选条目"
                          : `选择 2 至 ${maxComparedEntities} 个条目生成对比表`}
                      </small>
                    </div>
                    <button
                      type="button"
                      className="icon-button"
                      title="清空比较"
                      aria-label="清空比较"
                      disabled={!renderedComparedIds.length}
                      onClick={() => {
                        setOptimisticComparedEntityIds([]);
                        onLocationChange(activeId, [], true);
                      }}
                    >
                      <X size={16} aria-hidden="true" />
                    </button>
                  </div>
                  <ScrollableTableRegion ariaLabel="对比列表内容" className="comparison-table">
                    <table aria-label="对比列表内容">
                      <thead>
                        <tr>
                          <th scope="col">比较</th>
                          <th scope="col">#</th>
                          <th scope="col">名称</th>
                          <th scope="col">类型</th>
                          <th scope="col">资料编号</th>
                          <th scope="col">更新时间</th>
                          <th scope="col" aria-label="操作" />
                        </tr>
                      </thead>
                      <tbody>
                        {selected.members.map((member, index) => {
                          const isCompared = renderedComparedIds.includes(member.entity.id);
                          return (
                            <tr key={member.id} className={isCompared ? "comparison-member-selected" : undefined}>
                              <td>
                                <input
                                  type="checkbox"
                                  checked={isCompared}
                                  aria-label={`纳入情报对比：${member.entity.name}`}
                                  aria-describedby={comparisonSelectionHelpId}
                                  onChange={(event) => setEntityCompared(member.entity.id, event.target.checked)}
                                />
                              </td>
                              <td>{index + 1}</td>
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
                              <td>{entityTypeLabels[member.entity.entity_type]}</td>
                              <td>{Object.values(member.entity.external_ids).join(" · ") || "-"}</td>
                              <td>{formatDate(member.entity.updated_at)}</td>
                              <td>
                                {selected.editable ? (
                                  <button
                                    className="icon-button"
                                    type="button"
                                    title="移出列表"
                                    aria-label={`移出 ${member.entity.name}`}
                                    disabled={changingSet}
                                    onClick={() => void removeEntity(member.entity)}
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
                        <strong id="collection-comparison-heading">研发情报对比</strong>
                        <small>根据当前可查看的信息实时生成</small>
                      </span>
                    </header>
                    <CollectionComparisonMatrix entities={comparedEntities} onOpenEntity={onOpenEntity} />
                  </section>
                </>
              ) : (
                <EmptyState title="列表为空" detail="搜索药物、靶点、机构或适应症并加入列表" />
              )}

              <div className="export-panel">
                <div>
                  <strong>导出列表</strong>
                  <small>{policy ? `单次最多 ${policy.max_records_per_export} 条` : "当前暂不支持导出"}</small>
                </div>
                {policy?.enabled ? (
                  <>
                    <select
                      value={exportFormat}
                      onChange={(event) => setExportFormat(event.target.value as ExportFormat)}
                      aria-label="导出格式"
                    >
                      {policy.allowed_formats.map((format) => (
                        <option key={format} value={format}>
                          {format.toUpperCase()}
                        </option>
                      ))}
                    </select>
                    <fieldset className="export-fields" aria-label="导出字段">
                      {comparisonAllowedFields.map((field) => (
                        <label className="check-control" key={field}>
                          <input
                            type="checkbox"
                            checked={exportFields.includes(field)}
                            disabled={requiredFields.has(field)}
                            onChange={(event) =>
                              setExportFields((current) =>
                                event.target.checked ? [...current, field] : current.filter((item) => item !== field),
                              )
                            }
                          />
                          {fieldLabels[field] ?? field}
                        </label>
                      ))}
                    </fieldset>
                    <button
                      className="primary-button"
                      type="button"
                      disabled={exportMutation.isPending || !selected.member_count}
                      onClick={() => void exportSet()}
                    >
                      <Download size={16} />
                      {exportMutation.isPending ? "生成中" : "导出"}
                    </button>
                  </>
                ) : null}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
