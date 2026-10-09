import { act, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { QueryResultSummary } from "../components/QueryResultSummary";
import { setLocale } from "../lib/i18n";

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

it("updates the query-time caption and caution while preserving the original timestamp and zero counts", () => {
  setLocale("en");
  const queriedAt = "2026-10-09T01:00:00Z";
  render(<QueryResultSummary total={0} offset={0} count={0} unit="records" queriedAt={queriedAt} />);
  const time = screen.getByText(/Query time/);
  expect(time).toHaveAttribute("dateTime", queriedAt);
  expect(time).toHaveAttribute("title", expect.stringContaining("not the source's last update"));
  act(() => setLocale("zh-CN"));
  expect(time).toHaveTextContent("查询时间");
  expect(time).toHaveAttribute("dateTime", queriedAt);
  expect(screen.getByText("0")).toBeInTheDocument();
  expect(screen.queryByText(/0–0/)).not.toBeInTheDocument();
});
