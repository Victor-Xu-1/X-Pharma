import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { loadDrugDossier, loadDrugPrograms } from "../lib/contracts/drugDossier";
import { setLocale } from "../lib/i18n";
import { DrugView } from "../views/DrugView";
import { TrialOutcomeSummary } from "../views/drug/TrialOutcomeSummary";
import { drugDossierFixture as dossier, drug } from "./fixtures/drugDossier";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/drugDossier", async (original) => ({
  ...(await original<typeof import("../lib/contracts/drugDossier")>()),
  loadDrugDossier: vi.fn(),
  loadDrugPrograms: vi.fn(),
}));
vi.mock("../components/MoleculeDepiction", () => ({
  MoleculeDepiction: ({ name, smiles }: { name: string; smiles: string }) => (
    <div role="img" aria-label={name} data-smiles={smiles} />
  ),
}));
const props: ComponentProps<typeof DrugView> = {
  drug,
  activeSection: "overview",
  programOffset: 0,
  onProgramOffsetChange: vi.fn(),
  onSectionChange: vi.fn(),
  onOpenEntity: vi.fn(),
  onOpenDrug: vi.fn(),
  onOpenTarget: vi.fn(),
  onOpenDisease: vi.fn(),
  onOpenOrganization: vi.fn(),
  onOpenTrial: vi.fn(),
  onOpenPatent: vi.fn(),
  onOpenDeal: vi.fn(),
  onOpenRegulatoryEvent: vi.fn(),
  onOpenNewsEvent: vi.fn(),
};
beforeEach(() => {
  setLocale("en");
  vi.mocked(loadDrugDossier).mockResolvedValue(dossier);
  vi.mocked(loadDrugPrograms).mockResolvedValue({
    items: dossier.programs,
    total: 1,
    limit: 100,
    offset: 0,
    as_of: dossier.as_of,
    query_schema_version: "pharma.drug.programs.v1",
    warnings: [],
  });
});
it("localizes the drug overview without translating scientific identity or repeating its queries", async () => {
  renderWithQueryClient(<DrugView {...props} />);
  await screen.findByRole("heading", { name: drug.name });
  expect(screen.getByRole("tablist", { name: "Drug dossier sections" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Drug overview" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("Molecular formula")).toBeInTheDocument();
  expect(screen.getByText("经治理的小分子候选药物")).toBeInTheDocument();
  expect(screen.getByText("全球 II 期启动")).toBeInTheDocument();
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("tab", { name: "药物概览" })).toHaveAttribute("aria-selected", "true");
  expect(loadDrugDossier).toHaveBeenCalledTimes(1);
});
it("respects recorded trial calendar precision and uses endpoint-neutral result captions", async () => {
  vi.mocked(loadDrugDossier).mockResolvedValue({
    ...dossier,
    clinical_trials: dossier.clinical_trials.map((trial) => ({
      ...trial,
      start_date: "2025-01-01T00:00:00Z",
      start_date_precision: "year",
      completion_date: "2026-07-01T00:00:00Z",
      completion_date_precision: "month",
      enrollment: 0,
      outcomes: [{ ...trial.outcomes[0], measure: "原始安全性 endpoint" }],
    })),
  });
  renderWithQueryClient(<DrugView {...props} activeSection="trials" />);
  const trials = await screen.findByRole("table", { name: "Drug-linked clinical trials" });
  expect(within(trials).getByText("2025", { exact: true })).toBeInTheDocument();
  expect(trials).toHaveTextContent("2026-07");
  expect(trials).not.toHaveTextContent("01/01/2025");
  expect(screen.getByRole("columnheader", { name: "Reported endpoint" })).toBeInTheDocument();
  expect(screen.getByText("原始安全性 endpoint")).toBeInTheDocument();
});
it("depicts the explicitly recorded isomeric structure when available", async () => {
  vi.mocked(loadDrugDossier).mockResolvedValue({
    ...dossier,
    structures: [{ ...dossier.structures[0], canonical_smiles: "FC(Cl)Br", isomeric_smiles: "F[C@H](Cl)Br" }],
  });
  renderWithQueryClient(<DrugView {...props} />);
  expect(await screen.findByRole("img", { name: drug.name })).toHaveAttribute("data-smiles", "F[C@H](Cl)Br");
});
it("rejects a returned dossier identity that does not belong to the requested entity", async () => {
  vi.mocked(loadDrugDossier).mockResolvedValue({
    ...dossier,
    entity: { ...dossier.entity, id: "foreign-drug", name: "FOREIGN SOURCE IDENTITY" },
  });
  renderWithQueryClient(<DrugView {...props} />);
  await screen.findByText("Drug dossier does not match the requested entity");
  expect(screen.queryByRole("heading", { name: "FOREIGN SOURCE IDENTITY" })).not.toBeInTheDocument();
});
it.each([401, 403])("hides a previously cached development page after real-transport %s denial", async (status) => {
  const { queryClient } = renderWithQueryClient(<DrugView {...props} activeSection="pipeline" />);
  await screen.findByRole("table", { name: "Drug indication and regional progress" });
  vi.mocked(loadDrugPrograms).mockRejectedValue(new ApiError("Raw denial", status, null));
  await act(async () => {
    await queryClient.invalidateQueries({ queryKey: ["drug-programs", drug.id] });
  });
  await waitFor(() => expect(document.querySelector(".drug-program-progress-region")).not.toBeInTheDocument());
  expect(document.querySelector(".drug-program-rights-region")).not.toBeInTheDocument();
});

it("keeps a route back when an out-of-range development page has no rows but the total is nonzero", async () => {
  vi.mocked(loadDrugPrograms).mockResolvedValue({
    items: [],
    total: 233,
    limit: 100,
    offset: 300,
    as_of: dossier.as_of,
    query_schema_version: "pharma.drug.programs.v1",
    warnings: [],
  });
  const onProgramOffsetChange = vi.fn();
  renderWithQueryClient(
    <DrugView {...props} activeSection="pipeline" programOffset={300} onProgramOffsetChange={onProgramOffsetChange} />,
  );
  const first = await screen.findByRole("button", { name: "First page" });
  fireEvent.click(first);
  expect(onProgramOffsetChange).toHaveBeenCalledWith(0);
  expect(screen.queryByText("No linked development programs")).not.toBeInTheDocument();
});
it("retains every registered indication rather than just the scalar primary indication", async () => {
  const program = {
    ...dossier.programs[0],
    indications: [
      { program_id: "program-1", phase: "phase_2", disease_entity_id: "disease-1", disease_name: "原始适应症一" },
      { program_id: "program-2", phase: "phase_1", disease_entity_id: "disease-2", disease_name: "原始适应症二" },
    ],
  };
  vi.mocked(loadDrugPrograms).mockResolvedValue({
    items: [program],
    total: 1,
    limit: 100,
    offset: 0,
    as_of: dossier.as_of,
    query_schema_version: "pharma.drug.programs.v1",
    warnings: [],
  });
  const onOpenDisease = vi.fn();
  renderWithQueryClient(<DrugView {...props} activeSection="pipeline" onOpenDisease={onOpenDisease} />);
  const progress = await screen.findByRole("table", { name: "Drug indication and regional progress" });
  fireEvent.click(await within(progress).findByRole("button", { name: "原始适应症二" }));
  expect(onOpenDisease).toHaveBeenCalledWith("disease-2");
  expect(within(progress).getByRole("button", { name: "原始适应症一" })).toBeInTheDocument();
});
it("lets researchers disclose every original result group without dropping duplicates or zeros", () => {
  const trial = {
    ...dossier.clinical_trials[0],
    outcomes: [
      {
        ...dossier.clinical_trials[0].outcomes[0],
        results: [
          { group_label: "原始组一", value: "0" },
          { group_label: "原始组二", value: "1" },
          { group_label: "原始组三", value: "0" },
        ],
      },
    ],
  };
  renderWithQueryClient(<TrialOutcomeSummary trial={trial} />);
  const disclosure = screen.getByText("All reported endpoints and groups");
  fireEvent.click(disclosure);
  expect(screen.getByText("原始组三: 0")).toBeInTheDocument();
});

it("rejects a development page with a foreign drug identity instead of rendering its rows", async () => {
  vi.mocked(loadDrugPrograms).mockResolvedValue({
    items: [{ ...dossier.programs[0], drug_entity_id: "foreign-drug", disease_name: "FOREIGN INDICATION" }],
    total: 1,
    limit: 100,
    offset: 0,
    as_of: dossier.as_of,
    query_schema_version: "pharma.drug.programs.v1",
  });
  renderWithQueryClient(<DrugView {...props} activeSection="pipeline" />);
  await screen.findByText("Development page does not match the requested drug or offset");
  expect(screen.queryByText("FOREIGN INDICATION")).not.toBeInTheDocument();
});

it("keeps a transient page failure explicit with the provider reason and last successful rows", async () => {
  const { queryClient } = renderWithQueryClient(<DrugView {...props} activeSection="pipeline" />);
  await screen.findByRole("table", { name: "Drug indication and regional progress" });
  await waitFor(() => expect(queryClient.getQueryState(["drug-programs", drug.id, 0])?.fetchStatus).toBe("idle"));
  vi.mocked(loadDrugPrograms).mockRejectedValue(new ApiError("原始 provider reason <EGFR>", 503, null));
  await act(async () => {
    await queryClient.invalidateQueries({ queryKey: ["drug-programs", drug.id] });
  });
  expect(await screen.findByRole("alert")).toHaveTextContent("原始 provider reason <EGFR>");
  expect(screen.getByRole("table", { name: "Drug indication and regional progress" })).toBeInTheDocument();
});
