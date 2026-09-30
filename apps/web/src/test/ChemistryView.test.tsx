import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { type ChemistrySearchResult, saveChemistrySearch, searchChemistry } from "../lib/contracts/chemistry";
import type { SavedSearchRead } from "../lib/generated";
import { ChemistryView } from "../views/ChemistryView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/chemistry", () => ({
  chemistryKeys: { search: (request: unknown) => ["chemistry", "search", request] },
  saveChemistrySearch: vi.fn(),
  searchChemistry: vi.fn(),
}));

vi.mock("../components/MoleculeDepiction", () => ({
  MoleculeDepiction: ({ name }: { name: string }) => <div data-testid="molecule">{name}</div>,
}));

vi.mock("../components/StructureEditor", () => ({
  StructureEditor: ({ onApply }: { onApply: (value: string) => void }) => (
    <button data-testid="structure-editor-sample" type="button" onClick={() => onApply("CC(=O)OC1=CC=CC=C1C(=O)O")}>
      应用示例结构
    </button>
  ),
}));

const result: ChemistrySearchResult = {
  mode: "similarity",
  normalized_query: "CC(=O)OC1=CC=CC=C1C(=O)O",
  items: [
    {
      id: "structure-1",
      entity_id: "entity-1",
      entity_name: "Aspirin",
      canonical_smiles: "CC(=O)OC1=CC=CC=C1C(=O)O",
      isomeric_smiles: "CC(=O)OC1=CC=CC=C1C(=O)O",
      standard_inchi: "InChI=1S/C9H8O4",
      standard_inchi_key: "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
      molecular_formula: "C9H8O4",
      molecular_weight: 180.159,
      exact_mass: 180.0423,
      structure_version: "structure-v1",
      standardization_version: "rdkit-2026.03.3/cleanup-fragment-uncharger-tautomer-v1",
      fingerprint_version: "morgan-r2-2048-v1",
      updated_at: "2026-07-16T00:00:00Z",
      similarity: 0.812,
    },
  ],
  count: 1,
  as_of: "2026-07-16T00:00:00Z",
  standardization_version: "rdkit-2026.03.3/cleanup-fragment-uncharger-tautomer-v1",
  fingerprint_version: "morgan-r2-2048-v1",
  similarity_threshold: 0.75,
};

beforeEach(() => {
  vi.mocked(searchChemistry).mockReset();
  vi.mocked(saveChemistrySearch).mockReset();
});

it("keeps expert text input available and submits a bounded similarity search", async () => {
  vi.mocked(searchChemistry).mockResolvedValue(result);
  const inspect = vi.fn();
  renderWithQueryClient(<ChemistryView onInspectEntity={inspect} />);

  fireEvent.click(screen.getByRole("button", { name: "相似结构" }));
  fireEvent.click(screen.getByRole("tab", { name: "高级输入" }));
  expect(screen.getByRole("slider", { name: "相似度阈值" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("SMILES"), { target: { value: result.normalized_query } });
  fireEvent.change(screen.getByRole("slider"), { target: { value: "0.75" } });
  fireEvent.click(screen.getByText("更多选项"));
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "10" } });
  fireEvent.click(screen.getByRole("button", { name: "检索" }));

  await waitFor(() =>
    expect(vi.mocked(searchChemistry).mock.calls[0]?.[0]).toEqual({
      mode: "similarity",
      query: result.normalized_query,
      threshold: 0.75,
      limit: 10,
    }),
  );
  expect(await screen.findByRole("heading", { name: "Aspirin" })).toBeInTheDocument();
  expect(screen.getByText("81.2")).toBeInTheDocument();
  expect(screen.getByText("C9H8O4")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "查看实体" }));
  expect(inspect).toHaveBeenCalledWith("entity-1");
  expect(screen.queryByText("rdkit-2026.03.3/cleanup-fragment-uncharger-tautomer-v1")).not.toBeInTheDocument();
  expect(screen.queryByText("structure-v1")).not.toBeInTheDocument();
});

it("uses an edited structure as the exact-search query", async () => {
  vi.mocked(searchChemistry).mockResolvedValue({ ...result, mode: "exact", similarity_threshold: null });
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);

  expect(screen.getByRole("tab", { name: "绘制结构" })).toHaveAttribute("aria-selected", "true");
  expect(screen.queryByRole("button", { name: "应用示例结构" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "打开结构画板" }));
  expect(await screen.findByRole("button", { name: "应用示例结构" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "应用示例结构" }).closest("form")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "应用示例结构" }));
  fireEvent.click(screen.getByRole("button", { name: "检索" }));

  await waitFor(() =>
    expect(vi.mocked(searchChemistry).mock.calls[0]?.[0]).toEqual({
      mode: "exact",
      query: result.normalized_query,
      threshold: 0.7,
      limit: 20,
    }),
  );
});

it("prevents an empty structure query before calling the API", () => {
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);
  expect(screen.getByRole("button", { name: "检索" })).toBeDisabled();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(searchChemistry).not.toHaveBeenCalled();
});

it.each([
  {
    mode: "exact" as const,
    inputLabel: "SMILES",
    query: "not-a-smiles",
    code: "invalid_smiles",
    message: "无法识别该 SMILES，请检查结构式后重试",
  },
  {
    mode: "substructure" as const,
    inputLabel: "SMARTS",
    query: "[invalid",
    code: "invalid_smarts",
    message: "无法识别该 SMARTS，请检查子结构表达式后重试",
  },
])(
  "shows a public-safe Chinese error for an invalid $inputLabel query",
  async ({ mode, inputLabel, query, code, message }) => {
    vi.mocked(searchChemistry).mockRejectedValue(
      new Error(JSON.stringify({ code, message: `Internal parser detail for ${code}` })),
    );
    renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);

    if (mode === "substructure") fireEvent.click(screen.getByRole("button", { name: "子结构" }));
    fireEvent.click(screen.getByRole("tab", { name: "高级输入" }));
    fireEvent.change(screen.getByLabelText(inputLabel), { target: { value: query } });
    fireEvent.click(screen.getByRole("button", { name: "检索" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(message);
    expect(alert).not.toHaveTextContent(code);
    expect(alert).not.toHaveTextContent("Internal parser detail");
    expect(screen.getByRole("button", { name: "保存结构检索" })).toBeDisabled();
  },
);

it("clears an invalid text query when returning to the structure board", async () => {
  vi.mocked(searchChemistry).mockRejectedValue(
    new Error(JSON.stringify({ code: "invalid_smiles", message: "Internal parser detail" })),
  );
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);

  fireEvent.click(screen.getAllByRole("tab")[1]);
  fireEvent.change(screen.getByLabelText("SMILES"), { target: { value: "not-a-smiles" } });
  const submit = document.querySelector<HTMLButtonElement>("form.chemistry-options button[type='submit']");
  if (!submit) throw new Error("Chemistry submit button was not rendered");
  fireEvent.click(submit);
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(submit).toBeEnabled();

  fireEvent.click(screen.getAllByRole("tab")[0]);

  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(submit).toBeDisabled();
  expect(await screen.findByTestId("structure-editor-sample")).toBeInTheDocument();
});

it("invalidates a successful result when any query-shaping draft value changes", async () => {
  vi.mocked(searchChemistry).mockImplementation(async (input) => ({
    ...result,
    mode: input.mode,
    normalized_query: input.query,
    similarity_threshold: input.threshold ?? null,
  }));
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);

  fireEvent.click(screen.getByRole("tab", { name: "高级输入" }));
  const input = screen.getByLabelText("SMILES");
  const submit = screen.getByRole("button", { name: "检索" });
  const save = screen.getByRole("button", { name: "保存结构检索" });

  fireEvent.change(input, { target: { value: "CCO" } });
  fireEvent.click(submit);
  expect(await screen.findByRole("heading", { name: "Aspirin" })).toBeInTheDocument();
  expect(save).toBeEnabled();

  fireEvent.change(input, { target: { value: "CCN" } });
  expect(screen.queryByRole("heading", { name: "Aspirin" })).not.toBeInTheDocument();
  expect(save).toBeDisabled();

  fireEvent.click(submit);
  await waitFor(() => expect(searchChemistry).toHaveBeenCalledTimes(2));
  expect(await screen.findByRole("heading", { name: "Aspirin" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "相似结构" }));
  expect(screen.queryByRole("heading", { name: "Aspirin" })).not.toBeInTheDocument();
  expect(save).toBeDisabled();

  fireEvent.click(submit);
  await waitFor(() => expect(searchChemistry).toHaveBeenCalledTimes(3));
  expect(await screen.findByRole("heading", { name: "Aspirin" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("slider", { name: "相似度阈值" }), { target: { value: "0.8" } });
  expect(screen.queryByRole("heading", { name: "Aspirin" })).not.toBeInTheDocument();
  expect(save).toBeDisabled();

  fireEvent.click(submit);
  await waitFor(() => expect(searchChemistry).toHaveBeenCalledTimes(4));
  expect(await screen.findByRole("heading", { name: "Aspirin" })).toBeInTheDocument();
  fireEvent.click(screen.getByText("更多选项"));
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "10" } });
  expect(screen.queryByRole("heading", { name: "Aspirin" })).not.toBeInTheDocument();
  expect(save).toBeDisabled();
});

it("allows saving a successful zero-result query", async () => {
  vi.mocked(searchChemistry).mockResolvedValue({
    ...result,
    mode: "exact",
    normalized_query: "CCO",
    items: [],
    count: 0,
    similarity_threshold: null,
  });
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} />);

  fireEvent.click(screen.getByRole("tab", { name: "高级输入" }));
  fireEvent.change(screen.getByLabelText("SMILES"), { target: { value: "CCO" } });
  fireEvent.click(screen.getByRole("button", { name: "检索" }));

  expect(await screen.findByText("没有符合条件的结构")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "保存结构检索" })).toBeEnabled();
});

it("restores a saved structure query without putting the structure in the route", async () => {
  vi.mocked(searchChemistry).mockResolvedValue(result);
  renderWithQueryClient(
    <ChemistryView
      onInspectEntity={vi.fn()}
      savedSearchId="550e8400-e29b-41d4-a716-446655440000"
      initialSearch={{
        mode: "similarity",
        query: result.normalized_query,
        threshold: 0.75,
        limit: 10,
      }}
    />,
  );

  await waitFor(() =>
    expect(vi.mocked(searchChemistry).mock.calls[0]?.[0]).toEqual({
      mode: "similarity",
      query: result.normalized_query,
      threshold: 0.75,
      limit: 10,
    }),
  );
  expect(screen.getByLabelText("SMILES")).toHaveValue(result.normalized_query);
  expect(await screen.findByRole("heading", { name: "Aspirin" })).toBeInTheDocument();
});

it("saves the submitted structure as a typed server-side search", async () => {
  vi.mocked(searchChemistry).mockResolvedValue(result);
  const saved: SavedSearchRead = {
    created_at: "2026-08-03T00:00:00Z",
    description: "",
    id: "550e8400-e29b-41d4-a716-446655440000",
    name: "Aspirin similarity",
    owner_user_id: "550e8400-e29b-41d4-a716-446655440001",
    query_json: {
      mode: "similarity",
      query: result.normalized_query,
      threshold: 0.75,
      limit: 20,
    },
    query_type: "chemistry_search",
    query_version: 1,
    updated_at: "2026-08-03T00:00:00Z",
    visibility: "private",
  };
  vi.mocked(saveChemistrySearch).mockResolvedValue(saved);
  const onSavedSearch = vi.fn();
  renderWithQueryClient(<ChemistryView onInspectEntity={vi.fn()} onSavedSearch={onSavedSearch} />);

  fireEvent.click(screen.getByRole("tab", { name: "高级输入" }));
  fireEvent.change(screen.getByLabelText("SMILES"), { target: { value: result.normalized_query } });
  fireEvent.click(screen.getByRole("button", { name: "检索" }));
  await screen.findByRole("heading", { name: "Aspirin" });
  fireEvent.click(screen.getByRole("button", { name: "保存结构检索" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: saved.name } });
  fireEvent.click(screen.getByLabelText("企业内共享该检索"));
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

  await waitFor(() =>
    expect(vi.mocked(saveChemistrySearch)).toHaveBeenCalledWith({
      name: saved.name,
      input: {
        mode: "exact",
        query: result.normalized_query,
        threshold: 0.7,
        limit: 20,
      },
      shared: true,
    }),
  );
  expect(onSavedSearch).toHaveBeenCalledWith(saved);
});
