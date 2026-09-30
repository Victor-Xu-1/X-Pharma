import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListPlus } from "lucide-react";
import { type FormEvent, useState } from "react";

import {
  addComparisonSetMembers,
  collectionsKeys,
  createComparisonSet,
  getComparisonSet,
  listComparisonSets,
} from "../lib/contracts/collections";
import { ComparisonSetPickerDialog } from "./ComparisonSetPickerDialog";

function comparisonFailureMessage(caught: unknown, fallback: string): string {
  if (!(caught instanceof Error)) return fallback;
  if (/already in this comparison set/i.test(caught.message)) {
    return "列表内容刚刚发生变化，请重新确认后再试";
  }
  if (/limited to \d+ entities/i.test(caught.message)) return "该对比列表已达到 20 个实体上限";
  if (/version|expected_version|changed concurrently/i.test(caught.message)) {
    return "列表内容已更新，请重新确认后再试";
  }
  return /[\u3400-\u9fff]/u.test(caught.message) ? caught.message : fallback;
}

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
  const queryClient = useQueryClient();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [comparisonSetId, setComparisonSetId] = useState("");
  const [comparisonError, setComparisonError] = useState("");
  const comparisonSets = useQuery({
    queryKey: collectionsKeys.sets,
    queryFn: ({ signal }) => listComparisonSets(signal),
    enabled: pickerOpen,
  });
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
  const editableComparisonSets = (comparisonSets.data ?? []).filter((item) => item.editable);
  const activeComparisonSetId =
    (comparisonSetId && editableComparisonSets.some((item) => item.id === comparisonSetId)
      ? comparisonSetId
      : editableComparisonSets[0]?.id) || "";
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
    if (addToComparison.isPending || createComparison.isPending) return;
    const selectedSet = editableComparisonSets.find((item) => item.id === activeComparisonSetId);
    if (!selectedSet || !selectedIds.length) return;
    setComparisonError("");
    try {
      const current = await getComparisonSet(selectedSet.id);
      queryClient.setQueryData(collectionsKeys.detail(current.id), current);
      const currentEntityIds = new Set(current.members.map((member) => member.entity.id));
      const entityIdsToAdd = selectedIds.filter((entityId) => !currentEntityIds.has(entityId));
      const skippedCount = selectedIds.length - entityIdsToAdd.length;
      if (!entityIdsToAdd.length) {
        onAdded(`所选实体均已在 ${current.name} 中，无需重复添加`);
        onComparisonReady?.(
          current.id,
          current.members.map((member) => member.entity.id),
        );
        setPickerOpen(false);
        return;
      }
      if (current.member_count + entityIdsToAdd.length > 20) {
        setComparisonError(`该列表还可添加 ${Math.max(0, 20 - current.member_count)} 个实体，请减少选择后重试`);
        return;
      }
      const detail = await addToComparison.mutateAsync({
        setId: current.id,
        entityIds: entityIdsToAdd,
        expectedVersion: current.version,
      });
      queryClient.setQueryData(collectionsKeys.detail(detail.id), detail);
      await queryClient.invalidateQueries({ queryKey: collectionsKeys.sets });
      onAdded(
        `${entityIdsToAdd.length} 个实体已加入 ${detail.name}${skippedCount ? `，已跳过 ${skippedCount} 个已存在实体` : ""}`,
      );
      onComparisonReady?.(
        detail.id,
        detail.members.map((member) => member.entity.id),
      );
      setPickerOpen(false);
    } catch (caught) {
      setComparisonError(comparisonFailureMessage(caught, "加入对比列表失败，请稍后重试"));
      await comparisonSets.refetch();
    }
  }

  async function createAndAdd(name: string, visibility: "private" | "tenant") {
    if (!selectedEntityIds.length || addToComparison.isPending || createComparison.isPending) return;
    setComparisonError("");
    try {
      const created = await createComparison.mutateAsync({ name, visibility });
      const detail = await addToComparison.mutateAsync({
        setId: created.id,
        entityIds: selectedIds,
        expectedVersion: created.version,
      });
      queryClient.setQueryData(collectionsKeys.detail(detail.id), detail);
      await queryClient.invalidateQueries({ queryKey: collectionsKeys.sets });
      onAdded(`${selectedEntityIds.length} 个实体已加入 ${detail.name}`);
      onComparisonReady?.(
        detail.id,
        detail.members.map((member) => member.entity.id),
      );
      setPickerOpen(false);
    } catch (caught) {
      setComparisonError(comparisonFailureMessage(caught, "创建对比列表失败，请稍后重试"));
      await comparisonSets.refetch();
    }
  }

  const pending = addToComparison.isPending || createComparison.isPending;

  return (
    <>
      <button
        className="table-result-action"
        type="button"
        disabled={!selectedEntityIds.length}
        onClick={() => {
          setComparisonError("");
          setPickerOpen(true);
        }}
      >
        <ListPlus size={14} />
        {selectedEntityIds.length ? `加入列表（${selectedEntityIds.length}）` : "加入列表"}
      </button>
      <ComparisonSetPickerDialog
        open={pickerOpen}
        selectedCount={selectedIds.length}
        alreadyPresentCount={alreadyPresentCount}
        newSelectedCount={newEntityIds.length}
        selectedSetMemberCount={selectedSetDetail?.member_count}
        sets={editableComparisonSets}
        selectedSetId={activeComparisonSetId}
        loading={comparisonSets.isFetching || Boolean(activeComparisonSetId && comparisonDetail.isFetching)}
        pending={pending}
        error={
          comparisonError || (comparisonSets.error || comparisonDetail.error ? "对比列表加载失败，请稍后重试" : "")
        }
        onSetChange={(value) => {
          setComparisonError("");
          setComparisonSetId(value);
        }}
        onClose={() => setPickerOpen(false)}
        onSubmit={submit}
        onCreateSet={createAndAdd}
      />
    </>
  );
}
