import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";

type Row = { id: string; entityId: string };
const rowId = (row: Row) => row.id;
const entityId = (row: Row) => row.entityId;

describe("usePagedEntitySelection", () => {
  it("preserves canonical selections across pages and removes duplicate entity rows", () => {
    const { result, rerender } = renderHook(
      ({ rows }: { rows: Row[] }) => usePagedEntitySelection(rows, rowId, entityId),
      { initialProps: { rows: [{ id: "row-1", entityId: "entity-1" }] } },
    );

    act(() => result.current.onSelectionChange(["row-1"]));
    expect(result.current.selectedRowIds).toEqual(["row-1"]);
    expect(result.current.selectedEntityIds).toEqual(["entity-1"]);

    rerender({ rows: [{ id: "row-2", entityId: "entity-2" }] });
    act(() => result.current.onSelectionChange([...result.current.selectedRowIds, "row-2"]));
    expect(result.current.selectedRowIds).toEqual(["row-1", "row-2"]);
    expect(result.current.selectedEntityIds).toEqual(["entity-1", "entity-2"]);

    rerender({ rows: [{ id: "row-3", entityId: "entity-1" }] });
    act(() => result.current.onSelectionChange([...result.current.selectedRowIds, "row-3"]));
    expect(result.current.selectedRowIds).toEqual(["row-2", "row-3"]);
    expect(result.current.selectedEntityIds).toEqual(["entity-2", "entity-1"]);

    act(() => result.current.onSelectionChange(["unknown-row"]));
    expect(result.current.selectedRowIds).toEqual([]);
    expect(result.current.selectedEntityIds).toEqual([]);
  });

  it("clears all staged rows and canonical entities together", () => {
    const { result } = renderHook(() =>
      usePagedEntitySelection(
        [
          { id: "row-1", entityId: "entity-1" },
          { id: "row-2", entityId: "entity-2" },
        ],
        rowId,
        entityId,
      ),
    );

    act(() => result.current.onSelectionChange(["row-1", "row-2"]));
    act(() => result.current.clearSelection());
    expect(result.current.selectedRowIds).toEqual([]);
    expect(result.current.selectedEntityIds).toEqual([]);
  });
});
