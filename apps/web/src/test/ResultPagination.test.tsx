import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { expect, it, vi } from "vitest";

import { ResultPagination } from "../components/ResultPagination";
import { renderWithQueryClient } from "./renderWithQueryClient";

it("navigates the complete result set and keeps the jump draft synchronized", () => {
  const onPageChange = vi.fn();

  function ControlledPagination() {
    const [offset, setOffset] = useState(0);
    return (
      <ResultPagination
        totalRows={1150}
        offset={offset}
        pageSize={100}
        notice="受数据授权限制"
        onPageChange={(nextOffset) => {
          onPageChange(nextOffset);
          setOffset(nextOffset);
        }}
        ariaLabel="测试结果分页"
      />
    );
  }

  renderWithQueryClient(<ControlledPagination />);

  const pagination = screen.getByRole("navigation", { name: "测试结果分页" });
  expect(screen.getByText("第 1 / 12 页")).toBeVisible();
  expect(screen.getByText("共 1150 条")).toBeVisible();
  expect(screen.getByTitle("受数据授权限制")).toBeVisible();
  expect(screen.getByRole("button", { name: "首页" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "上一页" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "第 1 页" })).toHaveAttribute("aria-current", "page");

  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(onPageChange).toHaveBeenLastCalledWith(100);
  expect(screen.getByText("第 2 / 12 页")).toBeVisible();
  expect(screen.getByLabelText("目标页码")).toHaveValue(2);

  fireEvent.change(screen.getByLabelText("目标页码"), { target: { value: "12" } });
  fireEvent.submit(screen.getByRole("form", { name: "跳转页码" }));
  expect(onPageChange).toHaveBeenLastCalledWith(1100);
  expect(screen.getByText("第 12 / 12 页")).toBeVisible();
  expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "末页" })).toBeDisabled();
  expect(pagination).toContainElement(screen.getByRole("button", { name: "第 12 页" }));
});

it("rejects an out-of-range or non-integer jump without issuing a query", () => {
  const onPageChange = vi.fn();
  renderWithQueryClient(<ResultPagination totalRows={205} offset={0} pageSize={100} onPageChange={onPageChange} />);

  fireEvent.change(screen.getByLabelText("目标页码"), { target: { value: "4" } });
  fireEvent.click(screen.getByRole("button", { name: "跳转" }));
  expect(screen.getByRole("alert")).toHaveTextContent("请输入 1 到 3 之间的页码");
  expect(screen.getByLabelText("目标页码")).toHaveAttribute("aria-invalid", "true");
  expect(onPageChange).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("目标页码"), { target: { value: "2.5" } });
  fireEvent.click(screen.getByRole("button", { name: "跳转" }));
  expect(screen.getByRole("alert")).toHaveTextContent("请输入 1 到 3 之间的页码");
  expect(onPageChange).not.toHaveBeenCalled();
});

it("normalizes a stale out-of-range URL offset to the last authoritative page", async () => {
  const onPageChange = vi.fn();

  function StalePagination() {
    const [offset, setOffset] = useState(999);
    return (
      <ResultPagination
        totalRows={205}
        offset={offset}
        pageSize={100}
        onPageChange={(nextOffset) => {
          onPageChange(nextOffset);
          setOffset(nextOffset);
        }}
      />
    );
  }

  renderWithQueryClient(<StalePagination />);

  await waitFor(() => expect(onPageChange).toHaveBeenCalledWith(200));
  expect(screen.getByText("第 3 / 3 页")).toBeVisible();
  expect(screen.getByLabelText("目标页码")).toHaveValue(3);
  expect(screen.getByRole("button", { name: "末页" })).toBeDisabled();
});
