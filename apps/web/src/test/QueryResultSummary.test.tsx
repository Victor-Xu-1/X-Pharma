import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { QueryResultSummary } from "../components/QueryResultSummary";

it("does not imply that query time is data freshness, or show a zero-to-zero page", () => {
  render(<QueryResultSummary total={0} offset={0} count={0} unit="项临床试验" queriedAt="2026-10-04T00:00:00Z" />);
  expect(screen.getByText(/查询时间/)).toHaveAttribute("datetime", "2026-10-04T00:00:00Z");
  expect(screen.getByText(/查询时间/)).toHaveAttribute("title", expect.stringContaining("不代表来源数据"));
  expect(screen.queryByText(/0-0|截止/)).not.toBeInTheDocument();
});
it("shows bounded page position for actual records", () => {
  render(<QueryResultSummary total={21} offset={20} count={1} unit="条研发项目" queriedAt="2026-10-04T00:00:00Z" />);
  expect(screen.getByText(/21–21/)).toBeInTheDocument();
});
