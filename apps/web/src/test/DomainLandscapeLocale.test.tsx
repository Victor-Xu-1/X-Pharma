import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { DomainLandscape } from "../components/DomainLandscape";
import { setLocale } from "../lib/i18n";

beforeEach(() => setLocale("en"));

it("updates statistics captions without replacing source values or replaying drill-down", () => {
  const onFilter = vi.fn();
  const onViewChange = vi.fn();
  render(
    <DomainLandscape
      domainId="source"
      ariaLabel="Source distribution"
      total={2}
      totalUnit="records"
      unitLabel="Records"
      sections={[
        {
          id: "venue",
          title: "Original venue",
          detail: "RAW_SOURCE_DETAIL",
          buckets: [
            { key: "venue-0", label: "原始会议名称", count: 0, share: 0 },
            { key: "__missing__", label: "RAW_MISSING_LABEL", count: 2, share: 1 },
          ],
          filterField: "venue",
        },
      ]}
      view="table"
      onViewChange={onViewChange}
      onFilter={onFilter}
    />,
  );
  const table = screen.getByRole("table", { name: "Original venue statistics" });
  expect(screen.getByRole("region", { name: "Original venue statistics scroll region" })).toHaveAttribute(
    "tabindex",
    "0",
  );
  expect(screen.getByText("Complete result set")).toBeInTheDocument();
  expect(within(table).getByRole("columnheader", { name: "Share" })).toBeInTheDocument();
  expect(within(table).getByRole("row", { name: /原始会议名称/ })).toHaveTextContent("0.0%");
  const buttons = within(table).getAllByRole("button", { name: "Filter" });
  expect(buttons[1]).toBeDisabled();
  fireEvent.click(buttons[0]);
  expect(onFilter).toHaveBeenCalledExactlyOnceWith("venue", "venue-0");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "Original venue统计表" })).toBe(table);
  expect(table).toHaveTextContent("原始会议名称");
  expect(table).toHaveTextContent("RAW_MISSING_LABEL");
  expect(screen.getByText("RAW_SOURCE_DETAIL")).toBeInTheDocument();
  expect(onFilter).toHaveBeenCalledTimes(1);
  expect(onViewChange).not.toHaveBeenCalled();
});

it("renders English empty distributions on the shared language authority", () => {
  render(
    <DomainLandscape
      domainId="empty"
      ariaLabel="Empty distribution"
      total={0}
      totalUnit="records"
      unitLabel="Records"
      sections={[{ id: "source", title: "Source", detail: "", buckets: [], filterField: null }]}
      view="chart"
      onViewChange={vi.fn()}
      onFilter={vi.fn()}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("No records to summarize for this query.");
  expect(screen.getByRole("button", { name: "Chart" })).toHaveAttribute("aria-pressed", "true");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("status")).toHaveTextContent("当前查询没有可统计的记录。");
});
