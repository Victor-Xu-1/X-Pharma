import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { FieldDifferences } from "../components/FactReviewComparison";

it("names the comparison scroll region and makes complete values keyboard reachable", () => {
  render(
    <FieldDifferences
      before={{ count: 0, enabled: false }}
      after={{ count: 1, enabled: true }}
      beforeTitle="历史记录"
      afterTitle="本次候选"
    />,
  );
  const region = screen.getByRole("region", { name: "历史记录与本次候选字段对照" });
  expect(region).toHaveAttribute("tabindex", "0");
  expect(region).toHaveClass("review-field-differences");
  region.focus();
  expect(region).toHaveFocus();
  expect(within(region).getByRole("columnheader", { name: "历史记录" })).toBeInTheDocument();
  expect(within(region).getByRole("columnheader", { name: "本次候选" })).toBeInTheDocument();
  expect(within(region).getByRole("cell", { name: "0" })).toBeInTheDocument();
  expect(within(region).getByRole("cell", { name: "false" })).toBeInTheDocument();
});

it("does not create a scroll focus target when there are no field differences", () => {
  render(
    <FieldDifferences
      before={{ value: 0 }}
      after={{ value: 0 }}
      beforeTitle="来源解析值"
      afterTitle="平台规范化结果"
    />,
  );
  expect(screen.getByText("业务字段一致；引证元数据另行保留。")).toBeInTheDocument();
  expect(screen.queryByRole("region")).not.toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("keeps untrusted difference values literal inside the named comparison", () => {
  render(
    <FieldDifferences
      before={{ note: "old" }}
      after={{ note: '<img src=x onerror="alert(1)">' }}
      beforeTitle="来源解析值"
      afterTitle="平台规范化结果"
    />,
  );
  const region = screen.getByRole("region", { name: "来源解析值与平台规范化结果字段对照" });
  expect(region).toHaveTextContent('<img src=x onerror="alert(1)">');
  expect(region.querySelector("img")).toBeNull();
});
