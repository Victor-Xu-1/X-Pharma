import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { EntitySearchInput } from "../components/EntitySearchInput";
import { ResearchStart } from "../components/ResearchStart";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { SecondaryFilters } from "../components/SecondaryFilters";
import { setLocale } from "../lib/i18n";
import { renderWithQueryClient } from "./renderWithQueryClient";

it("keeps an invalid page draft and translates its existing validation without navigating", () => {
  const onPageChange = vi.fn();
  render(<ResultPagination totalRows={120} offset={0} pageSize={10} onPageChange={onPageChange} />);
  fireEvent.change(screen.getByLabelText("目标页码"), { target: { value: "20" } });
  fireEvent.click(screen.getByRole("button", { name: "跳转" }));
  act(() => setLocale("en"));
  expect(screen.getByRole("alert")).toHaveTextContent("Enter a page number between 1 and 12.");
  expect(screen.getByLabelText("Target page")).toHaveValue(20);
  expect(screen.getByText("Page 1 of 12")).toBeInTheDocument();
  expect(onPageChange).not.toHaveBeenCalled();
});

it("keeps a disclosed filter and its draft when changing labels", () => {
  render(
    <SecondaryFilters activeCount={2}>
      <input aria-label="raw draft" defaultValue="中文 EGFR" />
    </SecondaryFilters>,
  );
  act(() => setLocale("en"));
  expect(screen.getByText("More filters")).toBeInTheDocument();
  expect(screen.getByText("Selected: 2")).toBeInTheDocument();
  expect(screen.getByLabelText("raw draft")).toHaveValue("中文 EGFR");
  expect(document.querySelector("details")).toHaveAttribute("open");
});

it("localizes filter operators while retaining exact researcher-supplied text", () => {
  render(
    <AppliedFiltersBar
      filters={[
        { field: "q", operator: "contains", value: "中文药物 EGFR" },
        { field: "has_results", operator: "eq", value: false },
      ]}
      labels={{ q: "Query", has_results: "Results" }}
    />,
  );
  act(() => setLocale("en"));
  expect(screen.getByRole("region", { name: "Applied query conditions" })).toBeInTheDocument();
  expect(screen.getByText("中文药物 EGFR")).toBeInTheDocument();
  expect(screen.getByText("No")).toBeInTheDocument();
});

it("retains scientific example strings as normal searches, not translated claims", () => {
  const onSearch = vi.fn();
  render(<ResearchStart onSearch={onSearch} />);
  act(() => setLocale("en"));
  fireEvent.click(screen.getByRole("button", { name: "Search example EGFR" }));
  expect(onSearch).toHaveBeenCalledExactlyOnceWith("EGFR");
  expect(screen.getByText("OSIMERTINIB")).toBeInTheDocument();
});

it("uses the actual entity-type scope for its placeholder, not the language of a display label", () => {
  setLocale("en");
  renderWithQueryClient(
    <EntitySearchInput
      query=""
      entityTypes={[]}
      domainLabel="All intelligence"
      onQueryChange={vi.fn()}
      onSearch={vi.fn()}
    />,
  );
  expect(screen.getByRole("combobox", { name: "Intelligence query" })).toHaveAttribute(
    "placeholder",
    "Search drugs, targets, organizations or external identifiers",
  );
});

it("translates an open saved-search dialog without losing its controlled name and sharing state", () => {
  render(
    <SavedSearchDialog
      open
      domainLabel="Entity"
      name="我的研究 EGFR"
      shared
      monitor
      pending={false}
      error=""
      onNameChange={vi.fn()}
      onSharedChange={vi.fn()}
      onMonitorChange={vi.fn()}
      onClose={vi.fn()}
      onSubmit={vi.fn()}
    />,
  );
  act(() => setLocale("en"));
  expect(screen.getByRole("dialog", { name: "Save current Entity search" })).toBeInTheDocument();
  expect(screen.getByLabelText("Name")).toHaveValue("我的研究 EGFR");
  expect(screen.getByLabelText("Share this search within your organization")).toBeChecked();
  expect(screen.getByLabelText("Also subscribe to related data changes")).toBeChecked();
});
