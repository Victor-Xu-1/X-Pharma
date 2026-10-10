import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { type ChemistrySearchResult, saveChemistrySearch, searchChemistry } from "../lib/contracts/chemistry";
import { setLocale } from "../lib/i18n";
import { ChemistryView } from "../views/ChemistryView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/chemistry", async (original) => ({
  ...(await original<typeof import("../lib/contracts/chemistry")>()),
  searchChemistry: vi.fn(),
  saveChemistrySearch: vi.fn(),
}));
vi.mock("../components/MoleculeDepiction", () => ({
  MoleculeDepiction: ({ name }: { name: string }) => <span>{name}</span>,
}));
const result: ChemistrySearchResult = {
  mode: "similarity",
  normalized_query: "C[C@H](O)C(=O)O",
  count: 1,
  as_of: "2026-10-10T00:00:00Z",
  similarity_threshold: 0.75,
  standardization_version: "ORIGINAL_STANDARDIZATION",
  fingerprint_version: "ORIGINAL_FINGERPRINT",
  items: [
    {
      id: "controlled-structure",
      entity_id: "controlled-entity",
      entity_name: "原始记录 <source>",
      canonical_smiles: "C[C@H](O)C(=O)O",
      isomeric_smiles: "C[C@H](O)C(=O)O",
      standard_inchi: "ORIGINAL_INCHI",
      standard_inchi_key: "ORIGINAL_INCHIKEY",
      molecular_formula: "C3H6O3",
      molecular_weight: 90.077,
      exact_mass: 90.031694052,
      structure_version: "ORIGINAL_STRUCTURE_VERSION",
      standardization_version: "ORIGINAL_STANDARDIZATION",
      fingerprint_version: "ORIGINAL_FINGERPRINT",
      updated_at: "2026-10-10T00:00:00Z",
      similarity: 0.812,
    },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  setLocale("en");
  vi.mocked(searchChemistry).mockResolvedValue(result);
});
it("does not present an initial not-run state after a submitted parser failure", async () => {
  vi.mocked(searchChemistry).mockRejectedValue(new Error(JSON.stringify({ code: "invalid_smiles" })));
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: "Advanced input" }));
  fireEvent.change(screen.getByRole("textbox", { name: "SMILES" }), { target: { value: "invalid-structure" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByRole("alert");
  expect(screen.queryByText("No structure query has been run")).not.toBeInTheDocument();
});
it("renders the complete first-visit chemistry control and empty-state framing in English", () => {
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);
  expect(screen.getByRole("tab", { name: "Draw structure" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Advanced input" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Exact match" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open structure editor" })).toBeInTheDocument();
  expect(screen.getByText("No structure query has been run")).toBeInTheDocument();
  expect(searchChemistry).not.toHaveBeenCalled();
});
it("retains the structure draft, threshold and disclosure while interface language changes", async () => {
  setLocale("zh-CN");
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: "高级输入" }));
  fireEvent.click(screen.getByRole("button", { name: "相似结构" }));
  fireEvent.change(screen.getByRole("textbox", { name: "SMILES" }), { target: { value: result.normalized_query } });
  fireEvent.change(screen.getByRole("slider", { name: "相似度阈值" }), { target: { value: "0.75" } });
  const details = document.querySelector(".chemistry-more-options");
  if (!(details instanceof HTMLDetailsElement)) throw Error("Chemistry disclosure missing");
  details.open = true;
  await act(async () => {
    setLocale("en");
  });
  expect(screen.getByRole("slider", { name: "Similarity threshold" })).toHaveValue("0.75");
  expect(screen.getByRole("textbox", { name: "SMILES" })).toHaveValue(result.normalized_query);
  expect(details.open).toBe(true);
  expect(screen.getByRole("tab", { name: "Advanced input" })).toHaveAttribute("aria-selected", "true");
  expect(searchChemistry).not.toHaveBeenCalled();
});
it("localizes a known public-safe parser error without replaying the rejected query", async () => {
  setLocale("zh-CN");
  vi.mocked(searchChemistry).mockRejectedValue(
    new Error(JSON.stringify({ code: "invalid_smiles", message: "PRIVATE_PARSER_DETAIL" })),
  );
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: "高级输入" }));
  fireEvent.change(screen.getByRole("textbox", { name: "SMILES" }), { target: { value: "invalid-structure" } });
  fireEvent.click(screen.getByRole("button", { name: "检索" }));
  await screen.findByRole("alert");
  await act(async () => {
    setLocale("en");
  });
  expect(screen.getByRole("alert")).toHaveTextContent(
    "This SMILES could not be parsed. Check the structure and try again.",
  );
  expect(screen.getByRole("alert")).not.toHaveTextContent("PRIVATE_PARSER_DETAIL");
  expect(searchChemistry).toHaveBeenCalledOnce();
});
it("preserves the returned exact mass and original identifiers rather than rounding source data to four decimals", async () => {
  setLocale("zh-CN");
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: "高级输入" }));
  fireEvent.change(screen.getByRole("textbox", { name: "SMILES" }), { target: { value: result.normalized_query } });
  fireEvent.click(screen.getByRole("button", { name: "检索" }));
  await screen.findByRole("heading", { name: "原始记录 <source>" });
  expect(screen.getByText("90.031694052", { exact: true })).toBeInTheDocument();
  expect(screen.getAllByText(result.normalized_query).length).toBeGreaterThan(0);
  expect(screen.getAllByText("ORIGINAL_INCHIKEY").length).toBeGreaterThan(0);
});
it("takes one synchronous save intent before two same-tick form submissions can create duplicate saved searches", async () => {
  setLocale("zh-CN");
  vi.mocked(saveChemistrySearch).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: "高级输入" }));
  fireEvent.change(screen.getByRole("textbox", { name: "SMILES" }), { target: { value: result.normalized_query } });
  fireEvent.click(screen.getByRole("button", { name: "检索" }));
  await screen.findByRole("heading", { name: "原始记录 <source>" });
  fireEvent.click(screen.getByRole("button", { name: "保存结构检索" }));
  fireEvent.change(screen.getByRole("textbox", { name: "名称" }), {
    target: { value: "Original saved title <source>" },
  });
  const form = screen.getByRole("button", { name: "确认保存" }).closest("form");
  if (!form) throw Error("Saved search form missing");
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  await waitFor(() => expect(saveChemistrySearch).toHaveBeenCalledOnce());
});
