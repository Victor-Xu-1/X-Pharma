import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { expect, it, vi } from "vitest";

import { type ColumnDef, VirtualDataTable } from "../components/VirtualDataTable";
import { sessionKeys } from "../lib/contracts/session";
import { renderWithQueryClient } from "./renderWithQueryClient";

type Row = { id: string; name: string; score: number };

const columns: ColumnDef<Row, unknown>[] = [
  { accessorKey: "name", header: "名称", size: 180 },
  { accessorKey: "score", header: "评分", size: 120 },
];

it("renders a keyboard-scrollable table and exposes deterministic sorting state", () => {
  renderWithQueryClient(
    <VirtualDataTable
      ariaLabel="测试结果"
      columns={columns}
      data={[
        { id: "2", name: "ZZZ", score: 1 },
        { id: "1", name: "AAA", score: 2 },
      ]}
      getRowId={(row) => row.id}
      maxHeight={320}
      preferenceKey="entity-search"
      totalRows={24}
    />,
  );

  expect(screen.getByRole("region", { name: "测试结果滚动区域" })).toHaveAttribute("tabindex", "0");
  expect(screen.getByText(/当前页 2 条 \/ 共 24 条 · 当前页未排序/)).toBeVisible();
  const table = screen.getByRole("table", { name: "测试结果" });
  expect(table).toHaveStyle({ width: "100%", minWidth: "300px" });
  expect(table.style.getPropertyValue("--virtual-table-columns")).toBe("minmax(180px, 180fr) minmax(120px, 120fr)");
  const nameHeader = within(table).getByRole("columnheader", { name: /名称/ });
  expect(nameHeader).toHaveAttribute("aria-sort", "none");

  fireEvent.click(within(nameHeader).getByRole("button"));

  expect(nameHeader).toHaveAttribute("aria-sort", "ascending");
  expect(screen.getByText(/当前页按名称升序/)).toBeVisible();
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows.map((row) => row.textContent)).toEqual(["AAA2", "ZZZ1"]);
  for (const row of rows) {
    expect(row.style.transform).toBe("");
    expect(row.style.height).toMatch(/^\d+(?:\.\d+)?px$/);
  }

  fireEvent.click(screen.getByText("列", { exact: true }));
  fireEvent.click(screen.getByRole("checkbox", { name: "显示列：评分" }));
  expect(within(table).queryByRole("columnheader", { name: /评分/ })).not.toBeInTheDocument();

  const columnsSummary = screen.getByText("列", { exact: true });
  const columnCheckbox = screen.getByRole("checkbox", { name: "显示列：评分" });
  columnCheckbox.focus();
  fireEvent.keyDown(columnCheckbox, { key: "Escape" });
  expect(columnsSummary.closest("details")).not.toHaveAttribute("open");
  expect(columnsSummary).toHaveFocus();
  fireEvent.click(columnsSummary);
  expect(screen.getByRole("checkbox", { name: "显示列：评分" })).not.toBeChecked();

  fireEvent.click(screen.getByRole("button", { name: "紧凑" }));
  expect(screen.getByRole("button", { name: "紧凑" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("table", { name: "测试结果" }).closest(".virtual-table-shell")).toHaveClass(
    "density-compact",
  );

  expect(window.localStorage.length).toBe(0);

  fireEvent.click(screen.getByRole("button", { name: "恢复表格默认视图" }));
  expect(within(table).getByRole("columnheader", { name: /评分/ })).toBeVisible();
  expect(screen.getByRole("button", { name: "标准" })).toHaveAttribute("aria-pressed", "true");
  expect(nameHeader).toHaveAttribute("aria-sort", "none");
});

it("renders a bounded window in one natural-flow canvas for both densities", () => {
  renderWithQueryClient(
    <VirtualDataTable
      ariaLabel="有界结果"
      columns={columns}
      data={Array.from({ length: 200 }, (_, index) => ({ id: String(index), name: `Row ${index}`, score: index }))}
      getRowId={(row) => row.id}
      maxHeight={320}
      preferenceKey="entity-search"
    />,
  );
  const table = screen.getByRole("table", { name: "有界结果" });
  const body = table.querySelector("tbody");
  expect(body).toHaveStyle({ height: "13600px", paddingTop: "0px" });
  const rendered = () => [...table.querySelectorAll<HTMLElement>(".virtual-table-data-row")];
  expect(rendered().length).toBeGreaterThan(0);
  expect(rendered().length).toBeLessThanOrEqual(Math.ceil(320 / 68) + 8);
  for (const row of rendered()) {
    expect(row).toHaveStyle({ height: "68px" });
    expect(row.style.transform).toBe("");
  }
  fireEvent.click(screen.getByRole("button", { name: "紧凑" }));
  expect(body).toHaveStyle({ height: "9200px", paddingTop: "0px" });
  expect(rendered().length).toBeLessThanOrEqual(Math.ceil(320 / 46) + 8);
  for (const row of rendered()) {
    expect(row).toHaveStyle({ height: "46px" });
    expect(row.style.transform).toBe("");
  }
});

it("hydrates validated presentation preferences from the authenticated user workspace", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        column_order: ["score", "name"],
        column_visibility: { name: false },
        density: "compact",
        persisted: true,
        preference_key: "clinical-trials",
        schema_version: 1,
        updated_at: "2026-07-29T04:00:00Z",
        version: 4,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  renderWithQueryClient(
    <VirtualDataTable
      ariaLabel="持久化结果"
      columns={columns}
      data={[{ id: "1", name: "AAA", score: 2 }]}
      getRowId={(row) => row.id}
      preferenceKey="clinical-trials"
    />,
    undefined,
    (queryClient) =>
      queryClient.setQueryData(sessionKeys.current, {
        mode: "local",
        user: {
          id: "analyst-1",
          tenant_id: "tenant-1",
          email: "analyst@example.test",
          display_name: "Analyst",
          role: "analyst",
        },
      }),
  );

  const table = screen.getByRole("table", { name: "持久化结果" });
  await waitFor(() => expect(table.closest(".virtual-table-shell")).toHaveClass("density-compact"));
  expect(within(table).queryByRole("columnheader", { name: /名称/ })).not.toBeInTheDocument();
  expect(within(table).getByRole("columnheader", { name: /评分/ })).toBeVisible();
  expect(within(table).getByRole("columnheader", { name: /评分/ })).toHaveAttribute("aria-sort", "none");
  expect(fetchMock).toHaveBeenCalledOnce();
  expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/v1/workspace/table-preferences/clinical-trials");
  expect(window.localStorage.length).toBe(0);
});

it("reorders columns with keyboard-operable controls and persists the effective order", () => {
  renderWithQueryClient(
    <VirtualDataTable
      ariaLabel="可配置列结果"
      columns={columns}
      data={[{ id: "1", name: "AAA", score: 2 }]}
      getRowId={(row) => row.id}
      preferenceKey="deals"
    />,
  );

  const table = screen.getByRole("table", { name: "可配置列结果" });
  expect(
    within(table)
      .getAllByRole("columnheader")
      .map((header) => header.textContent),
  ).toEqual(["名称", "评分"]);

  fireEvent.click(screen.getByText("列", { exact: true }));
  expect(screen.getByRole("button", { name: "上移列：名称" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "上移列：评分" }));

  expect(
    within(table)
      .getAllByRole("columnheader")
      .map((header) => header.textContent),
  ).toEqual(["评分", "名称"]);
  expect(screen.getByRole("button", { name: "上移列：评分" })).toBeDisabled();
  expect(window.localStorage.length).toBe(0);

  fireEvent.click(screen.getByRole("button", { name: "恢复表格默认视图" }));
  expect(
    within(table)
      .getAllByRole("columnheader")
      .map((header) => header.textContent),
  ).toEqual(["名称", "评分"]);
});

it("delegates all-results sorting without reordering the current page locally", () => {
  const onSortingChange = vi.fn();
  const sorting = [{ id: "name", desc: true }];
  renderWithQueryClient(
    <VirtualDataTable
      ariaLabel="服务端排序结果"
      columns={columns}
      data={[
        { id: "2", name: "AAA", score: 1 },
        { id: "1", name: "ZZZ", score: 2 },
      ]}
      getRowId={(row) => row.id}
      preferenceKey="epidemiology"
      totalRows={240}
      sorting={sorting}
      defaultSorting={sorting}
      onSortingChange={onSortingChange}
      sortingScope="all"
    />,
  );

  expect(screen.getByText(/当前页 2 条 \/ 共 240 条 · 全部结果按名称降序/)).toBeVisible();
  const table = screen.getByRole("table", { name: "服务端排序结果" });
  const nameHeader = within(table).getByRole("columnheader", { name: /名称/ });
  expect(nameHeader).toHaveAttribute("aria-sort", "descending");
  expect(
    within(table)
      .getAllByRole("row")
      .slice(1)
      .map((row) => row.textContent),
  ).toEqual(["AAA1", "ZZZ2"]);

  fireEvent.click(screen.getByText("排序", { exact: true }));
  expect(screen.getByLabelText("第 1 排序字段")).toHaveValue("name");
  expect(screen.getByRole("button", { name: "第 1 排序方向：降序" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.change(screen.getByLabelText("第 1 排序字段"), { target: { value: "score" } });
  fireEvent.click(screen.getByRole("button", { name: "第 1 排序方向：升序" }));
  fireEvent.click(screen.getByRole("button", { name: "添加排序字段" }));
  expect(screen.getByLabelText("第 2 排序字段")).toHaveValue("name");
  fireEvent.click(screen.getByRole("button", { name: "第 2 排序方向：降序" }));
  fireEvent.click(screen.getByRole("button", { name: "上移第 2 排序字段" }));
  const sortSummary = screen.getByText("排序", { exact: true });
  const sortField = screen.getByLabelText("第 1 排序字段");
  sortField.focus();
  fireEvent.keyDown(sortField, { key: "Escape" });
  expect(sortSummary.closest("details")).not.toHaveAttribute("open");
  expect(sortSummary).toHaveFocus();
  fireEvent.click(sortSummary);
  expect(screen.getByLabelText("第 1 排序字段")).toHaveValue("name");
  expect(screen.getByLabelText("第 2 排序字段")).toHaveValue("score");
  expect(onSortingChange).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "应用排序" }));
  expect(onSortingChange).toHaveBeenCalledWith([
    { id: "name", desc: true },
    { id: "score", desc: false },
  ]);
  fireEvent.click(screen.getByRole("button", { name: "删除第 2 排序字段" }));
  expect(screen.getByRole("button", { name: "应用排序" })).toBeDisabled();
  onSortingChange.mockClear();

  fireEvent.click(within(nameHeader).getByRole("button"));
  expect(onSortingChange).toHaveBeenCalledWith([{ id: "name", desc: false }]);
});

it("persists a reset before server sorting can navigate away", async () => {
  const events: string[] = [];
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
    if ((init?.method ?? "GET") === "PUT") {
      events.push("put");
      return new Response(
        JSON.stringify({
          column_order: [],
          column_visibility: {},
          density: "comfortable",
          persisted: true,
          preference_key: "patent-families",
          schema_version: 1,
          updated_at: "2026-07-29T04:01:00Z",
          version: 3,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(
      JSON.stringify({
        column_order: [],
        column_visibility: { score: false },
        density: "compact",
        persisted: true,
        preference_key: "patent-families",
        schema_version: 1,
        updated_at: "2026-07-29T04:00:00Z",
        version: 2,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  });
  const onSortingChange = vi.fn(() => events.push("sort"));
  renderWithQueryClient(
    <VirtualDataTable
      ariaLabel="服务端重置结果"
      columns={columns}
      data={[{ id: "1", name: "AAA", score: 2 }]}
      preferenceKey="patent-families"
      sorting={[{ id: "name", desc: false }]}
      defaultSorting={[]}
      onSortingChange={onSortingChange}
      sortingScope="all"
      defaultSortingDescription="按相关性降序"
    />,
    undefined,
    (queryClient) =>
      queryClient.setQueryData(sessionKeys.current, {
        mode: "local",
        user: {
          id: "analyst-1",
          tenant_id: "tenant-1",
          email: "analyst@example.test",
          display_name: "Analyst",
          role: "analyst",
        },
      }),
  );

  await waitFor(() => expect(screen.getByRole("button", { name: "紧凑" })).toHaveAttribute("aria-pressed", "true"));
  fireEvent.click(screen.getByRole("button", { name: "恢复表格默认视图" }));

  await waitFor(() => expect(onSortingChange).toHaveBeenCalledWith([]));
  const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(JSON.parse(String(put?.[1]?.body))).toEqual({
    column_order: [],
    column_visibility: {},
    density: "comfortable",
    expected_version: 2,
    schema_version: 1,
  });
  expect(events).toEqual(["put", "sort"]);
});

it("surfaces a preference save failure and retries the current view", async () => {
  let putCount = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
    if ((init?.method ?? "GET") === "PUT") {
      putCount += 1;
      if (putCount === 1) return new Response(JSON.stringify({ detail: "unavailable" }), { status: 503 });
      return new Response(
        JSON.stringify({
          column_order: [],
          column_visibility: {},
          density: "compact",
          persisted: true,
          preference_key: "regulatory-events",
          schema_version: 1,
          updated_at: "2026-07-29T04:01:00Z",
          version: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(
      JSON.stringify({
        column_order: [],
        column_visibility: {},
        density: "comfortable",
        persisted: false,
        preference_key: "regulatory-events",
        schema_version: 1,
        updated_at: null,
        version: 0,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  });
  renderWithQueryClient(
    <VirtualDataTable
      ariaLabel="保存失败结果"
      columns={columns}
      data={[{ id: "1", name: "AAA", score: 2 }]}
      preferenceKey="regulatory-events"
    />,
    undefined,
    (queryClient) =>
      queryClient.setQueryData(sessionKeys.current, {
        mode: "local",
        user: {
          id: "analyst-1",
          tenant_id: "tenant-1",
          email: "analyst@example.test",
          display_name: "Analyst",
          role: "analyst",
        },
      }),
  );

  await waitFor(() => expect(screen.getByRole("button", { name: "紧凑" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "紧凑" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("视图设置保存失败"), { timeout: 2_000 });

  fireEvent.click(screen.getByRole("button", { name: "重试" }));

  await waitFor(() => expect(screen.queryByText("视图设置保存失败")).not.toBeInTheDocument());
  expect(putCount).toBe(2);
  expect(screen.getByRole("button", { name: "紧凑" })).toHaveAttribute("aria-pressed", "true");
});

it("controls accessible row selection across the virtualized current page", () => {
  function SelectionTable() {
    const [selectedRowIds, setSelectedRowIds] = useState<string[]>([]);
    return (
      <VirtualDataTable
        ariaLabel="可选择结果"
        columns={columns}
        data={[
          { id: "1", name: "AAA", score: 2 },
          { id: "2", name: "BBB", score: 1 },
        ]}
        getRowId={(row) => row.id}
        preferenceKey="news-events"
        rowSelection={{
          selectedRowIds,
          onChange: setSelectedRowIds,
          getRowLabel: (row) => row.name,
          label: "选择候选条目",
        }}
      />
    );
  }

  renderWithQueryClient(<SelectionTable />);

  const selectPage = screen.getByRole("checkbox", { name: "选择当前页" }) as HTMLInputElement;
  fireEvent.click(screen.getByRole("checkbox", { name: "选择AAA" }));
  expect(screen.getByText("已选 1 项")).toBeVisible();
  expect(selectPage.indeterminate).toBe(true);
  expect(screen.getByRole("checkbox", { name: "取消选择AAA" })).toBeChecked();

  fireEvent.click(selectPage);
  expect(screen.getByText("已选 2 项")).toBeVisible();
  expect(screen.getByRole("checkbox", { name: "取消选择AAA" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "取消选择BBB" })).toBeChecked();
  expect(screen.getAllByRole("row").filter((row) => row.classList.contains("is-selected"))).toHaveLength(2);

  fireEvent.click(screen.getByRole("button", { name: "清除已选项" }));
  expect(screen.getByText("选择候选条目")).toBeVisible();
  expect(screen.getByRole("checkbox", { name: "选择AAA" })).not.toBeChecked();
});
