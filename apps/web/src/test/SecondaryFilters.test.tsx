import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { SecondaryFilters } from "../components/SecondaryFilters";

it("keeps secondary controls collapsed until requested", () => {
  render(
    <SecondaryFilters activeCount={0}>
      <label>
        语言
        <input />
      </label>
    </SecondaryFilters>,
  );
  expect(screen.getByText("更多筛选").closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText("按需展开")).toBeInTheDocument();
});

it.each([1, 3])("reveals %s existing URL conditions rather than hiding them", (activeCount) => {
  render(
    <SecondaryFilters activeCount={activeCount}>
      <label>
        语言
        <input defaultValue="中文" />
      </label>
    </SecondaryFilters>,
  );
  expect(screen.getByText("更多筛选").closest("details")).toHaveAttribute("open");
  expect(screen.getByText(`已选 ${activeCount} 项`)).toBeInTheDocument();
});

it("keeps edited controls mounted and does not submit the surrounding query", () => {
  const submit = vi.fn();
  const { rerender } = render(
    <form onSubmit={submit}>
      <SecondaryFilters activeCount={0}>
        <label>
          语言
          <input defaultValue="中文" />
        </label>
      </SecondaryFilters>
    </form>,
  );
  const input = screen.getByLabelText("语言");
  fireEvent.change(input, { target: { value: "英文" } });
  fireEvent.click(screen.getByText("更多筛选"));
  expect(submit).not.toHaveBeenCalled();
  rerender(
    <form onSubmit={submit}>
      <SecondaryFilters activeCount={1}>
        <label>
          语言
          <input defaultValue="中文" />
        </label>
      </SecondaryFilters>
    </form>,
  );
  expect(screen.getByLabelText("语言")).toBe(input);
  expect(input).toHaveValue("英文");
  expect(document.querySelectorAll("form")).toHaveLength(1);
});
