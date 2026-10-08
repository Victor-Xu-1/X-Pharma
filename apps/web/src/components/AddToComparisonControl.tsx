import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListPlus } from "lucide-react";
import { type FormEvent, useEffect, useLayoutEffect, useRef, useState } from "react";
import { type ComparisonFeedback, comparisonFailure, comparisonFeedbackText } from "../lib/comparisonFeedback";
import {
  addComparisonSetMembers,
  collectionsKeys,
  createComparisonSet,
  getComparisonSet,
} from "../lib/contracts/collections";
import { useMessages } from "../lib/i18n";
import { comparisonMessages, comparisonText } from "../lib/i18n/comparison";
import { useCollectionCatalog } from "../lib/useCollectionCatalog";
import { CollectionDirectoryControls } from "./CollectionDirectoryControls";
import { ComparisonSetPickerDialog } from "./ComparisonSetPickerDialog";

function uniqueEntityIds(entityIds: string[]): string[] {
  return [...new Set(entityIds)];
}

/**
 * Shared "add selected rows to a comparison set" control.
 *
 * Every structured work domain whose rows map to canonical entities reuses this exact
 * flow: the button opens the governed picker, the write carries the set's expected
 * version, version conflicts surface in-dialog for recovery, and success clears the
 * selection through `onAdded`.
 */
export function AddToComparisonControl({
  selectedEntityIds,
  onAdded,
  onComparisonReady,
}: {
  selectedEntityIds: string[];
  onAdded: (message: string) => void;
  onComparisonReady?: (comparisonSetId: string, entityIds: string[]) => void;
}) {
  const t = useMessages(comparisonMessages);
  const queryClient = useQueryClient();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [comparisonSetId, setComparisonSetId] = useState("");
  const [comparisonError, setComparisonError] = useState<ComparisonFeedback | null>(null);
  const catalog = useCollectionCatalog(pickerOpen, true);
  const comparisonSets = catalog.query;
  const lock = useRef(false);
  const [busy, setBusy] = useState(false);
  const signature = uniqueEntityIds(selectedEntityIds).join("|");
  const live = useRef({ mounted: true, open: pickerOpen, signature, generation: 0 });
  useLayoutEffect(() => {
    if (live.current.open !== pickerOpen || live.current.signature !== signature) live.current.generation += 1;
    live.current.open = pickerOpen;
    live.current.signature = signature;
  });
  useEffect(() => {
    live.current.mounted = true;
    return () => {
      live.current.mounted = false;
      live.current.generation += 1;
    };
  }, []);
  const addToComparison = useMutation({
    mutationFn: ({
      setId,
      entityIds,
      expectedVersion,
    }: {
      setId: string;
      entityIds: string[];
      expectedVersion: number;
    }) => addComparisonSetMembers(setId, { entity_ids: entityIds, expected_version: expectedVersion }),
  });
  const createComparison = useMutation({
    mutationFn: ({ name, visibility }: { name: string; visibility: "private" | "tenant" }) =>
      createComparisonSet({ name, visibility }),
  });
  const editableComparisonSets = (comparisonSets.data?.items ?? []).filter((item) => item.editable);
  const activeComparisonSetId = comparisonSetId || editableComparisonSets[0]?.id || "";
  useEffect(() => {
    if (pickerOpen && !comparisonSetId && activeComparisonSetId) setComparisonSetId(activeComparisonSetId);
  }, [activeComparisonSetId, comparisonSetId, pickerOpen]);
  const comparisonDetail = useQuery({
    queryKey: collectionsKeys.detail(activeComparisonSetId),
    queryFn: ({ signal }) => getComparisonSet(activeComparisonSetId, signal),
    enabled: pickerOpen && Boolean(activeComparisonSetId),
  });
  const selectedSetDetail = comparisonDetail.data?.id === activeComparisonSetId ? comparisonDetail.data : null;
  const selectedIds = uniqueEntityIds(selectedEntityIds);
  const existingIds = new Set(selectedSetDetail?.members.map((member) => member.entity.id) ?? []);
  const newEntityIds = selectedIds.filter((entityId) => !existingIds.has(entityId));
  const alreadyPresentCount = selectedIds.length - newEntityIds.length;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current || !selectedSetDetail?.editable || !selectedIds.length) return;
    lock.current = true;
    setBusy(true);
    const generation = live.current.generation;
    const stillHere = () => live.current.mounted && live.current.generation === generation;
    setComparisonError(null);
    try {
      const current = await getComparisonSet(activeComparisonSetId);
      queryClient.setQueryData(collectionsKeys.detail(current.id), current);
      if (!stillHere()) return;
      const currentEntityIds = new Set(current.members.map((member) => member.entity.id));
      const entityIdsToAdd = selectedIds.filter((entityId) => !currentEntityIds.has(entityId));
      const skippedCount = selectedIds.length - entityIdsToAdd.length;
      if (!entityIdsToAdd.length) {
        if (!stillHere()) return;
        onAdded(comparisonText("所选实体均已在 {name} 中，无需重复添加", { name: current.name }));
        onComparisonReady?.(
          current.id,
          current.members.map((member) => member.entity.id),
        );
        setPickerOpen(false);
        return;
      }
      if (current.member_count + entityIdsToAdd.length > 20) {
        if (stillHere())
          setComparisonError({
            key: "该列表还可添加 {count} 个实体，请减少选择后重试",
            parameters: { count: Math.max(0, 20 - current.member_count) },
          });
        return;
      }
      const detail = await addToComparison.mutateAsync({
        setId: current.id,
        entityIds: entityIdsToAdd,
        expectedVersion: current.version,
      });
      queryClient.setQueryData(collectionsKeys.detail(detail.id), detail);
      await queryClient.invalidateQueries({ queryKey: collectionsKeys.catalogs });
      if (!stillHere()) return;
      onAdded(
        comparisonText("{count} 个实体已加入 {name}", { count: entityIdsToAdd.length, name: detail.name }) +
          (skippedCount ? comparisonText("，已跳过 {count} 个已存在实体", { count: skippedCount }) : ""),
      );
      onComparisonReady?.(
        detail.id,
        detail.members.map((member) => member.entity.id),
      );
      setPickerOpen(false);
    } catch (caught) {
      await queryClient.invalidateQueries({ queryKey: collectionsKeys.detail(activeComparisonSetId), exact: true });
      if (stillHere()) {
        setComparisonError(comparisonFailure(caught, "加入对比列表失败，请稍后重试"));
        await comparisonSets.refetch();
      }
    } finally {
      lock.current = false;
      if (live.current.mounted) setBusy(false);
    }
  }

  async function createAndAdd(name: string, visibility: "private" | "tenant") {
    if (!selectedEntityIds.length || lock.current) return;
    lock.current = true;
    setBusy(true);
    const generation = live.current.generation;
    const stillHere = () => live.current.mounted && live.current.generation === generation;
    let createdId = "";
    setComparisonError(null);
    try {
      const created = await createComparison.mutateAsync({ name, visibility });
      createdId = created.id;
      queryClient.setQueryData(collectionsKeys.detail(created.id), created);
      if (stillHere()) setComparisonSetId(created.id);
      const detail = await addToComparison.mutateAsync({
        setId: created.id,
        entityIds: selectedIds,
        expectedVersion: created.version,
      });
      queryClient.setQueryData(collectionsKeys.detail(detail.id), detail);
      await queryClient.invalidateQueries({ queryKey: collectionsKeys.catalogs });
      if (!stillHere()) return;
      onAdded(comparisonText("{count} 个实体已加入 {name}", { count: selectedEntityIds.length, name: detail.name }));
      onComparisonReady?.(
        detail.id,
        detail.members.map((member) => member.entity.id),
      );
      setPickerOpen(false);
    } catch (caught) {
      if (stillHere()) {
        setComparisonError(
          createdId
            ? { created: comparisonFailure(caught, "成员写入失败") }
            : comparisonFailure(caught, "创建对比列表失败，请稍后重试"),
        );
        await comparisonSets.refetch();
      }
    } finally {
      lock.current = false;
      if (live.current.mounted) setBusy(false);
    }
  }

  const pending = busy;
  const availableSets =
    selectedSetDetail?.editable && !editableComparisonSets.some((item) => item.id === selectedSetDetail.id)
      ? [selectedSetDetail, ...editableComparisonSets]
      : editableComparisonSets;

  return (
    <>
      <button
        className="table-result-action"
        type="button"
        disabled={pending || !selectedEntityIds.length}
        onClick={() => {
          setComparisonError(null);
          setComparisonSetId("");
          setPickerOpen(true);
        }}
      >
        <ListPlus size={14} />
        {selectedEntityIds.length ? t("加入列表（{count}）", { count: selectedEntityIds.length }) : t("加入列表")}
      </button>
      <ComparisonSetPickerDialog
        open={pickerOpen}
        selectedCount={selectedIds.length}
        alreadyPresentCount={alreadyPresentCount}
        newSelectedCount={newEntityIds.length}
        selectedSetMemberCount={selectedSetDetail?.member_count}
        sets={availableSets}
        selectedSetId={activeComparisonSetId}
        loading={comparisonSets.isFetching || Boolean(activeComparisonSetId && comparisonDetail.isFetching)}
        pending={pending}
        error={
          comparisonFeedbackText(comparisonError) ||
          (comparisonSets.error || comparisonDetail.error ? t("对比列表加载失败，请稍后重试") : "")
        }
        onSetChange={(value) => {
          setComparisonError(null);
          setComparisonSetId(value);
        }}
        onClose={() => setPickerOpen(false)}
        onSubmit={submit}
        onCreateSet={createAndAdd}
        catalogControls={<CollectionDirectoryControls catalog={catalog} pending={pending} />}
      />
    </>
  );
}
