import { useCallback, useMemo, useState } from "react";

type EntitySelectionState = {
  rowIds: string[];
  entityIdByRowId: Map<string, string>;
};

const emptySelection = (): EntitySelectionState => ({ rowIds: [], entityIdByRowId: new Map() });

export function usePagedEntitySelection<Row>(
  rows: readonly Row[],
  getRowId: (row: Row) => string,
  getEntityId: (row: Row) => string,
) {
  const [selection, setSelection] = useState<EntitySelectionState>(emptySelection);
  const currentEntityIdByRowId = useMemo(
    () => new Map(rows.map((row) => [getRowId(row), getEntityId(row)])),
    [getEntityId, getRowId, rows],
  );

  const onSelectionChange = useCallback(
    (nextRowIds: string[]) => {
      setSelection((current) => {
        if (!nextRowIds.length) return emptySelection();

        const requested = new Set(nextRowIds);
        const entityIdByRowId = new Map<string, string>();
        const rowIds: string[] = [];

        for (const rowId of current.rowIds) {
          if (!requested.has(rowId)) continue;
          const entityId = current.entityIdByRowId.get(rowId);
          if (!entityId) continue;
          entityIdByRowId.set(rowId, entityId);
          rowIds.push(rowId);
        }

        for (const rowId of nextRowIds) {
          if (entityIdByRowId.has(rowId)) continue;
          const entityId = currentEntityIdByRowId.get(rowId) ?? current.entityIdByRowId.get(rowId);
          if (!entityId) continue;

          // A canonical entity may occur in several domain rows. Keep the most recently
          // selected visible row so one entity consumes exactly one comparison slot.
          const duplicateRowId = rowIds.find((candidate) => entityIdByRowId.get(candidate) === entityId);
          if (duplicateRowId) {
            entityIdByRowId.delete(duplicateRowId);
            rowIds.splice(rowIds.indexOf(duplicateRowId), 1);
          }
          entityIdByRowId.set(rowId, entityId);
          rowIds.push(rowId);
        }

        return { rowIds, entityIdByRowId };
      });
    },
    [currentEntityIdByRowId],
  );

  const selectedEntityIds = useMemo(
    () => selection.rowIds.flatMap((rowId) => selection.entityIdByRowId.get(rowId) ?? []),
    [selection],
  );
  const clearSelection = useCallback(() => setSelection(emptySelection()), []);

  return {
    selectedRowIds: selection.rowIds,
    selectedEntityIds,
    onSelectionChange,
    clearSelection,
  };
}
