import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { setLocale } from "../lib/i18n";
import { TargetPipelineDateRange, TargetPipelineSelect } from "../views/target/pipeline/PipelineFilterControls";
import { geographyLabel, organizationRoleLabel } from "../views/target/pipeline/presentation";

it("updates standalone date captions without changing source group names, ISO values or callbacks", () => {
  const from = vi.fn(),
    to = vi.fn();
  render(
    <TargetPipelineDateRange
      legend="Source-owned date group"
      from="2026-01-01"
      to="2026-02-01"
      onFromChange={from}
      onToChange={to}
    />,
  );
  act(() => setLocale("en"));
  expect(screen.getByLabelText("Source-owned date group From")).toHaveValue("2026-01-01");
  expect(screen.getByLabelText("Source-owned date group To")).toHaveValue("2026-02-01");
  expect(screen.getByText("Source-owned date group")).toBeVisible();
  act(() => setLocale("zh-CN"));
  expect(screen.getByLabelText("Source-owned date group起")).toHaveValue("2026-01-01");
  expect(from).not.toHaveBeenCalled();
  expect(to).not.toHaveBeenCalled();
});

it("localizes standalone select captions while preserving unknown selected values and zero counts", () => {
  const change = vi.fn();
  render(
    <TargetPipelineSelect
      label="Source-owned category"
      value="FUTURE_VALUE"
      values={{ FUTURE_VALUE: 0 }}
      onChange={change}
    />,
  );
  act(() => setLocale("en"));
  expect(screen.getByRole("option", { name: "All" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "FUTURE_VALUE (0)" })).toBeEnabled();
  expect(screen.getByRole("combobox", { name: "Source-owned category" })).toHaveValue("FUTURE_VALUE");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("option", { name: "全部" })).toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
});

it("preserves unrecognized geographic and organization-role source codes rather than inventing a known category", () => {
  setLocale("en");
  expect(geographyLabel("FUTURE_REGION")).toBe("FUTURE_REGION");
  expect(organizationRoleLabel("FUTURE_ROLE")).toBe("FUTURE_ROLE");
});
