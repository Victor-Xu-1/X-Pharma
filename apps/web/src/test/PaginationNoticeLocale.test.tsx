import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ResultPagination } from "../components/ResultPagination";
import { setLocale } from "../lib/i18n";
import { PUBLIC_COVERAGE_NOTICE } from "../lib/publicWarnings";

it("translates the known product notice in place but leaves raw source notices unchanged", () => {
  setLocale("en");
  const onPageChange = vi.fn();
  const rendered = render(
    <ResultPagination
      totalRows={1}
      offset={0}
      pageSize={100}
      notice={PUBLIC_COVERAGE_NOTICE}
      onPageChange={onPageChange}
    />,
  );
  expect(screen.getByTitle("Results may be limited by source coverage and update timing.")).toBeVisible();
  act(() => setLocale("zh-CN"));
  expect(screen.getByTitle(PUBLIC_COVERAGE_NOTICE)).toBeVisible();
  rendered.rerender(
    <ResultPagination totalRows={1} offset={0} pageSize={100} notice="原始来源 notice" onPageChange={onPageChange} />,
  );
  act(() => setLocale("en"));
  expect(screen.getByTitle("原始来源 notice")).toBeVisible();
  expect(onPageChange).not.toHaveBeenCalled();
});
