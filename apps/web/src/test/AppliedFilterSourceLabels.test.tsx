import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { setLocale } from "../lib/i18n";

it("keeps unknown/prototype-like applied fields and values literal across language switching", () => {
  setLocale("en");
  const onClear = vi.fn();
  render(
    <AppliedFiltersBar
      filters={[
        { field: "constructor", operator: "eq", value: "__proto__" },
        { field: "kind", operator: "in", value: ["ACTIVE", "constructor", "RAW_FUTURE_CODE"] },
      ]}
      labels={{ kind: "Kind" }}
      valueLabels={{ kind: { ACTIVE: "Active" } }}
      onClear={onClear}
    />,
  );
  const region = screen.getByRole("region");
  expect(region).toHaveTextContent("constructor");
  expect(region).toHaveTextContent("__proto__");
  expect(region).toHaveTextContent("RAW_FUTURE_CODE");
  expect(region).toHaveTextContent("Active");
  act(() => setLocale("zh-CN"));
  expect(region).toHaveTextContent("constructor");
  expect(region).toHaveTextContent("RAW_FUTURE_CODE");
  expect(onClear).not.toHaveBeenCalled();
});
