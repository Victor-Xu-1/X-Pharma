import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { EmptyQueryResult } from "../components/EmptyQueryResult";

it("distinguishes a blank organization from a filtered empty result without making an absence claim", () => {
  const onClear = vi.fn();
  const { rerender } = render(<EmptyQueryResult domain="临床试验" filtered={false} onClear={onClear} />);
  expect(screen.getByText("暂无可查询的临床试验")).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  rerender(<EmptyQueryResult domain="临床试验" filtered onClear={onClear} />);
  expect(screen.getByText(/不代表相关研究不存在/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "清除筛选条件" }));
  expect(onClear).toHaveBeenCalledOnce();
});
