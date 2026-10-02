import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type ColumnDef,
  type ColumnOrderState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
  type VisibilityState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronDown,
  ChevronsUpDown,
  ChevronUp,
  CloudOff,
  Columns3,
  List,
  LoaderCircle,
  Plus,
  RefreshCw,
  RotateCcw,
  Rows3,
  Trash2,
  X,
} from "lucide-react";
import { type CSSProperties, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  defaultWorkspaceTablePreference,
  loadWorkspaceTablePreference,
  saveWorkspaceTablePreference,
  type WorkspaceTableDensity,
  type WorkspaceTablePreferenceKey,
  type WorkspaceTablePreferences,
  workspacePreferenceKeys,
} from "../lib/contracts/workspacePreferences";
import { useSessionIdentity } from "./SessionIdentityContext";

type TablePreferences = WorkspaceTablePreferences;

type TableRowSelection<T> = {
  selectedRowIds: readonly string[];
  onChange: (rowIds: string[]) => void;
  getRowLabel: (row: T) => string;
  label?: string;
  maxSelectedRows?: number;
  allowSelectAll?: boolean;
};

const defaultPreferences: TablePreferences = { columnVisibility: {}, density: "comfortable", columnOrder: [] };

function columnLabel(column: { id: string; columnDef: { header?: unknown } }): string {
  return typeof column.columnDef.header === "string" ? column.columnDef.header : column.id;
}

function sameStringArray(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function normalizeColumnOrder(columnOrder: ColumnOrderState, defaultColumnOrder: string[]): ColumnOrderState {
  const knownColumns = new Set(defaultColumnOrder);
  const normalized = columnOrder.filter((columnId, index) => {
    return knownColumns.has(columnId) && columnOrder.indexOf(columnId) === index;
  });
  for (const columnId of defaultColumnOrder) {
    if (!normalized.includes(columnId)) normalized.push(columnId);
  }
  return sameStringArray(normalized, defaultColumnOrder) ? [] : normalized;
}

function normalizeColumnVisibility(columnVisibility: VisibilityState, columnIds: string[]): VisibilityState {
  const knownColumns = new Set(columnIds);
  return Object.fromEntries(
    Object.entries(columnVisibility).filter(([columnId, visible]) => knownColumns.has(columnId) && !visible),
  );
}

function tablePreferenceFingerprint(preferences: TablePreferences): string {
  return JSON.stringify({
    columnOrder: preferences.columnOrder,
    columnVisibility: Object.fromEntries(
      Object.entries(preferences.columnVisibility).sort(([left], [right]) => {
        return left.localeCompare(right);
      }),
    ),
    density: preferences.density,
  });
}

function normalizeSortingState(sorting: SortingState): SortingState {
  const seen = new Set<string>();
  return sorting.filter((criterion) => {
    if (!criterion.id || seen.has(criterion.id) || seen.size >= 5) return false;
    seen.add(criterion.id);
    return true;
  });
}

export function VirtualDataTable<T>({
  ariaLabel,
  columns,
  data,
  getRowId,
  maxHeight = 560,
  preferenceKey,
  totalRows = data.length,
  sorting: controlledSorting,
  defaultSorting = [],
  onSortingChange,
  sortingScope = "page",
  defaultSortingDescription,
  toolbarActions,
  rowSelection,
}: {
  ariaLabel: string;
  columns: ColumnDef<T, unknown>[];
  data: T[];
  getRowId?: (row: T) => string;
  maxHeight?: number;
  preferenceKey: WorkspaceTablePreferenceKey;
  totalRows?: number;
  sorting?: SortingState;
  defaultSorting?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;
  sortingScope?: "page" | "all";
  defaultSortingDescription?: string;
  toolbarActions?: ReactNode;
  rowSelection?: TableRowSelection<T>;
}) {
  const queryClient = useQueryClient();
  const user = useSessionIdentity();
  const userId = user?.id ?? null;
  const ownerScope = user ? `${user.tenant_id}:${user.id}` : "anonymous";
  const preferenceQueryKey = workspacePreferenceKeys.table(ownerScope, preferenceKey);
  const preferenceIdentity = user ? `${ownerScope}:${preferenceKey}` : null;
  const preferenceQuery = useQuery({
    queryKey: preferenceQueryKey,
    queryFn: ({ signal }) => loadWorkspaceTablePreference(preferenceKey, signal),
    enabled: userId !== null,
  });
  const savePreference = useMutation({
    mutationFn: ({ expectedVersion, preferences }: { expectedVersion: number; preferences: TablePreferences }) =>
      saveWorkspaceTablePreference(preferenceKey, preferences, expectedVersion),
    onSuccess: (snapshot) => queryClient.setQueryData(preferenceQueryKey, snapshot),
  });
  const [hydratedPreferenceIdentity, setHydratedPreferenceIdentity] = useState<string | null>(null);
  const [localSorting, setLocalSorting] = useState<SortingState>(defaultSorting);
  const serverSorting = controlledSorting !== undefined && onSortingChange !== undefined;
  const sorting = serverSorting ? controlledSorting : localSorting;
  const [sortDraft, setSortDraft] = useState<SortingState>(sorting);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [density, setDensity] = useState<WorkspaceTableDensity>("comfortable");
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>([]);
  const [columnOrderAnnouncement, setColumnOrderAnnouncement] = useState("");
  const lastServerPreferenceFingerprint = useRef<string | null>(null);
  const scrollElement = useRef<HTMLDivElement>(null);
  const table = useReactTable({
    data,
    columns,
    getRowId,
    state: { sorting, columnVisibility, columnOrder },
    onSortingChange: (updater) => {
      const next = normalizeSortingState(typeof updater === "function" ? updater(sorting) : updater);
      if (serverSorting) onSortingChange?.(next.length ? next : defaultSorting);
      else setLocalSorting(next);
    },
    onColumnVisibilityChange: setColumnVisibility,
    onColumnOrderChange: setColumnOrder,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: serverSorting ? undefined : getSortedRowModel(),
    manualSorting: serverSorting,
    enableMultiSort: true,
    enableSortingRemoval: false,
    maxMultiSortColCount: 5,
  });
  const rows = table.getRowModel().rows;
  const selectedRowIds = rowSelection?.selectedRowIds ?? [];
  const selectedRowIdSet = useMemo(() => new Set(selectedRowIds), [selectedRowIds]);
  const pageRowIds = useMemo(() => rows.map((row) => row.id), [rows]);
  const selectedPageRowIds = pageRowIds.filter((rowId) => selectedRowIdSet.has(rowId));
  const allPageRowsSelected = pageRowIds.length > 0 && selectedPageRowIds.length === pageRowIds.length;
  const somePageRowsSelected = selectedPageRowIds.length > 0 && !allPageRowsSelected;
  const selectionColumnWidth = rowSelection ? 44 : 0;
  const rowHeight = density === "compact" ? 46 : 68;
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollElement.current,
    estimateSize: () => rowHeight,
    overscan: 8,
    initialRect: { width: 1000, height: maxHeight },
  });
  const measuredItems = virtualizer.getVirtualItems();
  const visibleItems = measuredItems.length
    ? measuredItems.map((item) => ({ index: item.index, size: item.size, start: item.start }))
    : rows
        .slice(0, Math.ceil(maxHeight / rowHeight) + 8)
        .map((_row, index) => ({ index, size: rowHeight, start: index * rowHeight }));
  const totalHeight = measuredItems.length ? virtualizer.getTotalSize() : rows.length * rowHeight;
  const width = table.getTotalSize() + selectionColumnWidth;
  const dataGridColumns = table
    .getVisibleLeafColumns()
    .map((column) => {
      const size = column.getSize();
      return `minmax(${size}px, ${size}fr)`;
    })
    .join(" ");
  const gridColumns = rowSelection ? `${selectionColumnWidth}px ${dataGridColumns}` : dataGridColumns;
  const tableStyle = {
    "--virtual-table-columns": gridColumns,
    width: "100%",
    minWidth: `${width}px`,
  } as CSSProperties;
  const flatColumns = table.getAllFlatColumns();
  const defaultColumnOrder = useMemo(
    () => flatColumns.filter((column) => column.columns.length === 0).map((column) => column.id),
    [flatColumns],
  );
  const normalizedColumnOrder = useMemo(
    () => normalizeColumnOrder(columnOrder, defaultColumnOrder),
    [columnOrder, defaultColumnOrder],
  );
  const normalizedColumnVisibility = useMemo(
    () => normalizeColumnVisibility(columnVisibility, defaultColumnOrder),
    [columnVisibility, defaultColumnOrder],
  );
  const leafColumns = table.getAllLeafColumns();
  const sortableColumns = leafColumns.filter((column) => column.getCanSort());
  const visibleColumnCount = leafColumns.filter((column) => column.getIsVisible()).length;
  const sortingIsDefault =
    sorting.length === defaultSorting.length &&
    sorting.every((sort, index) => sort.id === defaultSorting[index]?.id && sort.desc === defaultSorting[index]?.desc);
  const presentationIsCustomized =
    density !== "comfortable" ||
    Object.values(normalizedColumnVisibility).includes(false) ||
    normalizedColumnOrder.length > 0;
  const hasCustomizedView = presentationIsCustomized || !sortingIsDefault;
  const currentPreferences = useMemo<TablePreferences>(
    () => ({
      columnOrder: normalizedColumnOrder,
      columnVisibility: normalizedColumnVisibility,
      density,
    }),
    [density, normalizedColumnOrder, normalizedColumnVisibility],
  );
  const currentPreferenceFingerprint = useMemo(
    () => tablePreferenceFingerprint(currentPreferences),
    [currentPreferences],
  );
  const serverPreferences = useMemo<TablePreferences>(() => {
    const preference = preferenceQuery.data ?? defaultWorkspaceTablePreference(preferenceKey);
    return {
      columnOrder: normalizeColumnOrder(preference.columnOrder, defaultColumnOrder),
      columnVisibility: normalizeColumnVisibility(preference.columnVisibility, defaultColumnOrder),
      density: preference.density,
    };
  }, [defaultColumnOrder, preferenceKey, preferenceQuery.data]);
  const serverPreferenceFingerprint = useMemo(() => tablePreferenceFingerprint(serverPreferences), [serverPreferences]);
  const preferenceReady = preferenceIdentity === null || hydratedPreferenceIdentity === preferenceIdentity;
  const preferenceControlsDisabled =
    !preferenceReady || (preferenceIdentity !== null && !preferenceQuery.data) || savePreference.isPending;
  const sortingScopeLabel = sortingScope === "all" ? "全部结果" : "当前页";
  const sortingDescription = sorting.length
    ? `${sortingScopeLabel}按${sorting
        .map((sort) => {
          const column = leafColumns.find((candidate) => candidate.id === sort.id);
          return `${column ? columnLabel(column) : sort.id}${sort.desc ? "降序" : "升序"}`;
        })
        .join("、")}`
    : defaultSortingDescription
      ? `${sortingScopeLabel}${defaultSortingDescription}`
      : `${sortingScopeLabel}未排序`;
  const draftSorting = sortDraft.length ? sortDraft : defaultSorting;
  const sortDraftIsCurrent =
    sorting.length === draftSorting.length &&
    sorting.every((sort, index) => sort.id === draftSorting[index]?.id && sort.desc === draftSorting[index]?.desc);

  useEffect(() => {
    setSortDraft((current) => {
      const normalized = normalizeSortingState(sorting);
      const unchanged =
        current.length === normalized.length &&
        current.every(
          (criterion, index) => criterion.id === normalized[index]?.id && criterion.desc === normalized[index]?.desc,
        );
      return unchanged ? current : normalized;
    });
  }, [sorting]);

  useEffect(() => {
    setHydratedPreferenceIdentity(null);
    lastServerPreferenceFingerprint.current = null;
    if (preferenceIdentity === null) return;
    setColumnVisibility({});
    setColumnOrder([]);
    setColumnOrderAnnouncement("");
    setDensity("comfortable");
  }, [preferenceIdentity]);

  useEffect(() => {
    if (preferenceIdentity === null || !preferenceQuery.data) return;
    const incomingFingerprint = serverPreferenceFingerprint;
    const firstHydration = hydratedPreferenceIdentity !== preferenceIdentity;
    const unchangedSinceLastServerRead =
      lastServerPreferenceFingerprint.current === null ||
      lastServerPreferenceFingerprint.current === currentPreferenceFingerprint;
    if (firstHydration || (unchangedSinceLastServerRead && currentPreferenceFingerprint !== incomingFingerprint)) {
      setColumnVisibility(serverPreferences.columnVisibility);
      setColumnOrder(serverPreferences.columnOrder);
      setDensity(serverPreferences.density);
      window.requestAnimationFrame(() => virtualizer.measure());
    }
    lastServerPreferenceFingerprint.current = incomingFingerprint;
    if (firstHydration) setHydratedPreferenceIdentity(preferenceIdentity);
  }, [
    currentPreferenceFingerprint,
    hydratedPreferenceIdentity,
    preferenceIdentity,
    preferenceQuery.data,
    serverPreferenceFingerprint,
    serverPreferences,
    virtualizer,
  ]);

  useEffect(() => {
    if (!sameStringArray(columnOrder, normalizedColumnOrder)) setColumnOrder(normalizedColumnOrder);
    if (JSON.stringify(columnVisibility) !== JSON.stringify(normalizedColumnVisibility)) {
      setColumnVisibility(normalizedColumnVisibility);
    }
  }, [columnOrder, columnVisibility, normalizedColumnOrder, normalizedColumnVisibility]);

  useEffect(() => {
    if (
      preferenceIdentity === null ||
      hydratedPreferenceIdentity !== preferenceIdentity ||
      !preferenceQuery.data ||
      savePreference.isPending ||
      savePreference.isError ||
      currentPreferenceFingerprint === serverPreferenceFingerprint
    ) {
      return;
    }
    const timeout = window.setTimeout(() => {
      savePreference.mutate({
        expectedVersion: preferenceQuery.data.version,
        preferences: currentPreferences,
      });
    }, 450);
    return () => window.clearTimeout(timeout);
  }, [
    currentPreferenceFingerprint,
    currentPreferences,
    hydratedPreferenceIdentity,
    preferenceIdentity,
    preferenceQuery.data,
    savePreference,
    serverPreferenceFingerprint,
  ]);

  function changeDensity(nextDensity: WorkspaceTableDensity) {
    setDensity(nextDensity);
    window.requestAnimationFrame(() => virtualizer.measure());
  }

  async function resetView() {
    const persistReset =
      presentationIsCustomized && preferenceIdentity !== null && preferenceQuery.data && preferenceReady;
    setColumnVisibility({});
    setColumnOrder([]);
    setColumnOrderAnnouncement("");
    changeDensity("comfortable");
    if (persistReset && preferenceQuery.data) {
      try {
        await savePreference.mutateAsync({
          expectedVersion: preferenceQuery.data.version,
          preferences: defaultPreferences,
        });
      } catch {
        return;
      }
    }
    if (serverSorting) onSortingChange?.(defaultSorting);
    else setLocalSorting(defaultSorting);
  }

  function retryPreferenceSave() {
    if (!preferenceQuery.data) return;
    savePreference.reset();
    savePreference.mutate({
      expectedVersion: preferenceQuery.data.version,
      preferences: currentPreferences,
    });
  }

  function moveColumn(columnId: string, direction: -1 | 1) {
    const currentOrder = leafColumns.map((column) => column.id);
    const sourceIndex = currentOrder.indexOf(columnId);
    const targetIndex = sourceIndex + direction;
    if (sourceIndex < 0 || targetIndex < 0 || targetIndex >= currentOrder.length) return;
    const nextOrder = [...currentOrder];
    [nextOrder[sourceIndex], nextOrder[targetIndex]] = [nextOrder[targetIndex], nextOrder[sourceIndex]];
    setColumnOrder(normalizeColumnOrder(nextOrder, defaultColumnOrder));
    const column = leafColumns[sourceIndex];
    setColumnOrderAnnouncement(`${columnLabel(column)}已移至第${targetIndex + 1}列`);
  }

  function changeRowSelection(rowId: string) {
    if (!rowSelection) return;
    if (selectedRowIdSet.has(rowId)) {
      rowSelection.onChange(selectedRowIds.filter((selectedId) => selectedId !== rowId));
      return;
    }
    if (rowSelection.maxSelectedRows && selectedRowIds.length >= rowSelection.maxSelectedRows) return;
    rowSelection.onChange([...selectedRowIds, rowId]);
  }

  function changePageSelection() {
    if (!rowSelection || rowSelection.allowSelectAll === false) return;
    if (allPageRowsSelected) {
      const pageIds = new Set(pageRowIds);
      rowSelection.onChange(selectedRowIds.filter((rowId) => !pageIds.has(rowId)));
      return;
    }
    const next = [...selectedRowIds];
    for (const rowId of pageRowIds) {
      if (next.includes(rowId)) continue;
      if (rowSelection.maxSelectedRows && next.length >= rowSelection.maxSelectedRows) break;
      next.push(rowId);
    }
    rowSelection.onChange(next);
  }

  function applyServerSort() {
    if (!serverSorting || sortDraftIsCurrent) return;
    onSortingChange?.(draftSorting);
  }

  function updateSortDraft(index: number, update: Partial<SortingState[number]>) {
    setSortDraft((current) =>
      normalizeSortingState(
        current.map((criterion, criterionIndex) =>
          criterionIndex === index ? { ...criterion, ...update } : criterion,
        ),
      ),
    );
  }

  function addSortCriterion() {
    const selected = new Set(sortDraft.map((criterion) => criterion.id));
    const nextColumn = sortableColumns.find((column) => !selected.has(column.id));
    if (!nextColumn || sortDraft.length >= 5) return;
    setSortDraft((current) => [...current, { id: nextColumn.id, desc: false }]);
  }

  function removeSortCriterion(index: number) {
    setSortDraft((current) => {
      const next = current.filter((_criterion, criterionIndex) => criterionIndex !== index);
      return next.length ? next : defaultSorting;
    });
  }

  function moveSortCriterion(index: number, direction: -1 | 1) {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= sortDraft.length) return;
    setSortDraft((current) => {
      const next = [...current];
      [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
      return next;
    });
  }

  return (
    <div className={`virtual-table-shell density-${density}${rowSelection ? " has-row-selection" : ""}`}>
      <header className="virtual-table-toolbar">
        <span aria-live="polite">
          当前页 {data.length} 条{totalRows > data.length ? ` / 共 ${totalRows} 条` : ""} · {sortingDescription}
        </span>
        {rowSelection ? (
          <div className="table-selection-status" aria-live="polite">
            <span>
              {selectedRowIds.length
                ? `已选 ${selectedRowIds.length}${rowSelection.maxSelectedRows ? `/${rowSelection.maxSelectedRows}` : ""} 项`
                : (rowSelection.label ?? "选择条目")}
            </span>
            {selectedRowIds.length ? (
              <button
                className="icon-button"
                type="button"
                aria-label="清除已选项"
                title="清除已选项"
                onClick={() => rowSelection.onChange([])}
              >
                <X size={14} />
              </button>
            ) : null}
          </div>
        ) : null}
        {toolbarActions}
        {preferenceQuery.isError ? (
          <div className="table-preference-error" role="alert">
            <CloudOff size={14} aria-hidden="true" />
            <span>视图设置同步失败</span>
            <button type="button" onClick={() => void preferenceQuery.refetch()}>
              <RefreshCw size={13} aria-hidden="true" />
              重试
            </button>
          </div>
        ) : savePreference.isError ? (
          <div className="table-preference-error" role="alert">
            <CloudOff size={14} aria-hidden="true" />
            <span>视图设置保存失败</span>
            <button type="button" onClick={retryPreferenceSave}>
              <RefreshCw size={13} aria-hidden="true" />
              重试
            </button>
          </div>
        ) : preferenceIdentity !== null && (!preferenceReady || savePreference.isPending) ? (
          <span className="table-preference-sync" role="status" title="正在同步视图设置">
            <LoaderCircle size={14} aria-hidden="true" />
            <span className="sr-only">正在同步视图设置</span>
          </span>
        ) : null}
        {serverSorting && sortableColumns.length ? (
          <details className="table-sort-menu">
            <summary title="自定义排序">
              <ChevronsUpDown size={15} />
              排序
            </summary>
            <fieldset className="table-sort-editor">
              <legend>自定义排序</legend>
              <div className="table-sort-editor-heading">
                <strong>排序优先级</strong>
                <span aria-live="polite">{sortDraft.length}/5</span>
              </div>
              <div className="table-sort-criteria">
                {sortDraft.map((criterion, index) => (
                  <div className="table-sort-criterion" key={criterion.id}>
                    <span className="table-sort-priority" aria-hidden="true">
                      {index + 1}
                    </span>
                    <label>
                      <span className="sr-only">第 {index + 1} 排序字段</span>
                      <select
                        aria-label={`第 ${index + 1} 排序字段`}
                        value={criterion.id}
                        onChange={(event) => updateSortDraft(index, { id: event.target.value })}
                      >
                        {sortableColumns.map((column) => (
                          <option
                            value={column.id}
                            key={column.id}
                            disabled={sortDraft.some(
                              (selected, selectedIndex) => selectedIndex !== index && selected.id === column.id,
                            )}
                          >
                            {columnLabel(column)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <fieldset className="table-sort-direction">
                      <legend className="sr-only">第 {index + 1} 排序方向</legend>
                      <button
                        type="button"
                        aria-label={`第 ${index + 1} 排序方向：升序`}
                        title="升序"
                        aria-pressed={!criterion.desc}
                        onClick={() => updateSortDraft(index, { desc: false })}
                      >
                        <ArrowUp size={14} />
                      </button>
                      <button
                        type="button"
                        aria-label={`第 ${index + 1} 排序方向：降序`}
                        title="降序"
                        aria-pressed={criterion.desc}
                        onClick={() => updateSortDraft(index, { desc: true })}
                      >
                        <ArrowDown size={14} />
                      </button>
                    </fieldset>
                    <div className="table-sort-order-controls">
                      <button
                        type="button"
                        aria-label={`上移第 ${index + 1} 排序字段`}
                        title="提高优先级"
                        disabled={index === 0}
                        onClick={() => moveSortCriterion(index, -1)}
                      >
                        <ChevronUp size={14} />
                      </button>
                      <button
                        type="button"
                        aria-label={`下移第 ${index + 1} 排序字段`}
                        title="降低优先级"
                        disabled={index === sortDraft.length - 1}
                        onClick={() => moveSortCriterion(index, 1)}
                      >
                        <ChevronDown size={14} />
                      </button>
                      <button
                        type="button"
                        aria-label={`删除第 ${index + 1} 排序字段`}
                        title="删除排序字段"
                        disabled={sortDraft.length === 1}
                        onClick={() => removeSortCriterion(index)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <button
                type="button"
                className="secondary-button table-sort-add"
                disabled={sortDraft.length >= 5 || sortDraft.length >= sortableColumns.length}
                onClick={addSortCriterion}
              >
                <Plus size={14} />
                添加排序字段
              </button>
              <button
                type="button"
                className="primary-button table-sort-apply"
                disabled={sortDraftIsCurrent}
                onClick={applyServerSort}
              >
                应用排序
              </button>
            </fieldset>
          </details>
        ) : null}
        <fieldset className="table-density-control">
          <legend className="sr-only">表格密度</legend>
          <button
            type="button"
            className={density === "comfortable" ? "active" : ""}
            disabled={preferenceControlsDisabled}
            onClick={() => changeDensity("comfortable")}
            aria-pressed={density === "comfortable"}
            title="标准密度"
          >
            <List size={15} />
            <span>标准</span>
          </button>
          <button
            type="button"
            className={density === "compact" ? "active" : ""}
            disabled={preferenceControlsDisabled}
            onClick={() => changeDensity("compact")}
            aria-pressed={density === "compact"}
            title="紧凑密度"
          >
            <Rows3 size={15} />
            <span>紧凑</span>
          </button>
        </fieldset>
        <details className="table-column-menu">
          <summary>
            <Columns3 size={15} />列
          </summary>
          <fieldset>
            <legend>列设置</legend>
            {leafColumns.map((column, index) => {
              const label = columnLabel(column);
              const visible = column.getIsVisible();
              return (
                <div className="table-column-option" key={column.id}>
                  <input
                    type="checkbox"
                    checked={visible}
                    disabled={preferenceControlsDisabled || (visible && visibleColumnCount === 1)}
                    aria-label={`显示列：${label}`}
                    onChange={column.getToggleVisibilityHandler()}
                  />
                  <span>{label}</span>
                  <fieldset className="table-column-order-controls">
                    <legend className="sr-only">调整列顺序：{label}</legend>
                    <button
                      type="button"
                      aria-label={`上移列：${label}`}
                      title={`上移${label}`}
                      disabled={preferenceControlsDisabled || index === 0}
                      onClick={() => moveColumn(column.id, -1)}
                    >
                      <ChevronUp size={13} />
                    </button>
                    <button
                      type="button"
                      aria-label={`下移列：${label}`}
                      title={`下移${label}`}
                      disabled={preferenceControlsDisabled || index === leafColumns.length - 1}
                      onClick={() => moveColumn(column.id, 1)}
                    >
                      <ChevronDown size={13} />
                    </button>
                  </fieldset>
                  {visible ? <Check size={13} aria-hidden="true" /> : null}
                </div>
              );
            })}
          </fieldset>
          <span className="sr-only" aria-live="polite">
            {columnOrderAnnouncement}
          </span>
        </details>
        <button
          className="icon-button table-view-reset"
          type="button"
          aria-label="恢复表格默认视图"
          title="恢复默认视图"
          disabled={preferenceControlsDisabled || !hasCustomizedView}
          onClick={() => void resetView()}
        >
          <RotateCcw size={15} />
        </button>
      </header>
      <section
        className="virtual-table-viewport"
        ref={scrollElement}
        style={{ maxHeight }}
        aria-label={`${ariaLabel}滚动区域`}
        // biome-ignore lint/a11y/noNoninteractiveTabindex: keyboard users need a focus target for the two-axis scroll container.
        tabIndex={0}
      >
        <table className="virtual-data-table" aria-label={ariaLabel} style={tableStyle}>
          <thead className="virtual-table-header">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr className="virtual-table-row" key={headerGroup.id}>
                {rowSelection ? (
                  <th className="virtual-table-heading virtual-table-selection-heading" scope="col">
                    {rowSelection.allowSelectAll === false ? (
                      <span className="sr-only">选择行</span>
                    ) : (
                      <input
                        type="checkbox"
                        checked={allPageRowsSelected}
                        ref={(element) => {
                          if (element) element.indeterminate = somePageRowsSelected;
                        }}
                        disabled={!pageRowIds.length}
                        aria-label={allPageRowsSelected ? "取消选择当前页" : "选择当前页"}
                        onChange={changePageSelection}
                      />
                    )}
                  </th>
                ) : null}
                {headerGroup.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  const sortIndex = header.column.getSortIndex();
                  return (
                    <th
                      className="virtual-table-heading"
                      scope="col"
                      aria-sort={
                        sortIndex === 0
                          ? sorted === "asc"
                            ? "ascending"
                            : sorted === "desc"
                              ? "descending"
                              : "none"
                          : "none"
                      }
                      key={header.id}
                    >
                      {header.isPlaceholder ? null : header.column.getCanSort() ? (
                        <button type="button" onClick={header.column.getToggleSortingHandler()}>
                          <span>{flexRender(header.column.columnDef.header, header.getContext())}</span>
                          {sorted === "asc" ? (
                            <ArrowUp size={14} />
                          ) : sorted === "desc" ? (
                            <ArrowDown size={14} />
                          ) : (
                            <ChevronsUpDown size={14} />
                          )}
                          {sorting.length > 1 && sorted ? (
                            <small className="sort-priority">{sortIndex + 1}</small>
                          ) : null}
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="virtual-table-body" style={{ height: totalHeight }}>
            {visibleItems.map((virtualRow) => {
              const row = rows[virtualRow.index];
              const rowSelected = selectedRowIdSet.has(row.id);
              const rowSelectionDisabled = Boolean(
                rowSelection?.maxSelectedRows && !rowSelected && selectedRowIds.length >= rowSelection.maxSelectedRows,
              );
              return (
                <tr
                  className={`virtual-table-row virtual-table-data-row${rowSelected ? " is-selected" : ""}`}
                  key={row.id}
                  style={{ height: virtualRow.size, transform: `translateY(${virtualRow.start}px)` }}
                >
                  {rowSelection ? (
                    <td className="virtual-table-cell virtual-table-selection-cell">
                      <input
                        type="checkbox"
                        checked={rowSelected}
                        disabled={rowSelectionDisabled}
                        aria-label={`${rowSelected ? "取消选择" : "选择"}${rowSelection.getRowLabel(row.original)}`}
                        onChange={() => changeRowSelection(row.id)}
                      />
                    </td>
                  ) : null}
                  {row.getVisibleCells().map((cell) => (
                    <td className="virtual-table-cell" key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export type { ColumnDef, SortingState, TableRowSelection };
