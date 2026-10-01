import { fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { EntitySearchInput } from "../components/EntitySearchInput";
import { suggestEntities } from "../lib/contracts/intelligence";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/intelligence", () => ({
  intelligenceKeys: { suggestions: (query: string, types: string[]) => ["suggestions", { query, types }] },
  suggestEntities: vi.fn(),
}));
beforeEach(() => {
  vi.mocked(suggestEntities).mockResolvedValue(["EGFR", "EGFR family"]);
});

function Harness({
  onSearch = vi.fn(),
  entityTypes = ["target"],
}: {
  onSearch?: (value: string) => void;
  entityTypes?: string[];
}) {
  const [query, setQuery] = useState("");
  return (
    <EntitySearchInput
      query={query}
      entityTypes={entityTypes}
      domainLabel="靶点"
      onQueryChange={setQuery}
      onSearch={onSearch}
    />
  );
}

it("immediately hides obsolete candidates before debounce and for short input", async () => {
  renderWithQueryClient(<Harness />);
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: "EGFR" } });
  await screen.findByRole("option", { name: /EGFR family/ });
  fireEvent.change(input, { target: { value: "ALK" } });
  expect(screen.queryByRole("option")).not.toBeInTheDocument();
  fireEvent.change(input, { target: { value: "A" } });
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("submits typed input unless a suggestion was explicitly selected by keyboard", async () => {
  const onSearch = vi.fn();
  renderWithQueryClient(<Harness onSearch={onSearch} />);
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: "EGFR" } });
  await screen.findByRole("option", { name: /EGFR family/ });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(onSearch).toHaveBeenLastCalledWith("EGFR");
  fireEvent.focus(input);
  await screen.findByRole("listbox");
  fireEvent.keyDown(input, { key: "ArrowDown" });
  fireEvent.keyDown(input, { key: "ArrowDown" });
  const selected = screen.getByRole("option", { name: /EGFR family/ });
  expect(selected).toHaveAttribute("aria-selected", "true");
  expect(input).toHaveAttribute("aria-activedescendant", selected.id);
  fireEvent.keyDown(input, { key: "Enter" });
  expect(onSearch).toHaveBeenLastCalledWith("EGFR family");
  expect(input).toHaveValue("EGFR family");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("closes with Escape without submitting or propagating dismissal to the parent", async () => {
  const onSearch = vi.fn();
  renderWithQueryClient(<Harness onSearch={onSearch} />);
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: "EGFR" } });
  await screen.findByRole("option", { name: /EGFR family/ });
  const parentKey = vi.fn();
  document.addEventListener("keydown", parentKey);
  try {
    fireEvent.keyDown(input, { key: "Escape" });
    expect(parentKey).not.toHaveBeenCalled();
  } finally {
    document.removeEventListener("keydown", parentKey);
  }
  expect(input).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(onSearch).not.toHaveBeenCalled();
});

it("hides cached candidates on failure and retries exactly once when requested", async () => {
  const { queryClient } = renderWithQueryClient(<Harness />);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "EGFR" } });
  await screen.findByRole("option", { name: /EGFR family/ });
  vi.mocked(suggestEntities).mockRejectedValueOnce(new Error("Lookup unavailable"));
  await queryClient.invalidateQueries({ queryKey: ["suggestions"] });
  await screen.findByText("联想暂不可用，可直接检索");
  expect(screen.queryByRole("option")).not.toBeInTheDocument();
  const attempts = vi.mocked(suggestEntities).mock.calls.length;
  fireEvent.click(screen.getByRole("button", { name: "重试联想" }));
  await screen.findByRole("option", { name: /EGFR family/ });
  expect(suggestEntities).toHaveBeenCalledTimes(attempts + 1);
  expect(screen.getByRole("combobox")).toHaveFocus();
});

it("does not carry keyboard selection into another cached domain's suggestions", async () => {
  const onSearch = vi.fn();
  const { queryClient, rerender } = renderWithQueryClient(<Harness onSearch={onSearch} />);
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: "EGFR" } });
  await screen.findByRole("option", { name: /EGFR family/ });
  fireEvent.keyDown(input, { key: "ArrowDown" });
  fireEvent.keyDown(input, { key: "ArrowDown" });
  queryClient.setQueryData(["suggestions", { query: "EGFR", types: ["drug"] }], ["Drug", "Drug family"]);
  rerender(<Harness onSearch={onSearch} entityTypes={["drug"]} />);
  expect(screen.getByRole("option", { name: /Drug family/ })).toHaveAttribute("aria-selected", "false");
  fireEvent.keyDown(input, { key: "Enter" });
  expect(onSearch).toHaveBeenLastCalledWith("EGFR");
});
