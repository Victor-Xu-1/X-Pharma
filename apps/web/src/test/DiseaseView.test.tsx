import { fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { loadDiseaseDossier } from "../lib/contracts/disease";
import type { Entity } from "../lib/types";
import type { DiseaseDossierSection } from "../lib/workspaceRouting";
import { DiseaseView } from "../views/DiseaseView";
import { disease, dossier } from "./fixtures/diseaseDossier";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/disease", () => ({
  diseaseKeys: { dossier: (diseaseId: string) => ["disease-dossier", diseaseId] },
  loadDiseaseDossier: vi.fn(),
}));

vi.mock("../components/RecordProvenanceDrawer", () => ({
  ProvenanceButton: ({ selection, onOpen }: { selection: unknown; onOpen: (value: unknown) => void }) => (
    <button type="button" aria-label="查看原始证据" onClick={() => onOpen(selection)}>
      证据
    </button>
  ),
  RecordProvenanceDrawer: ({ selection }: { selection: { label: string } }) => (
    <div role="dialog" aria-label="原始证据面板">
      {selection.label}
    </div>
  ),
}));

function renderDiseaseView(
  entity: Entity | null = disease,
  initialSection: DiseaseDossierSection = "overview",
  callbacks: {
    onOpenEntity?: (entityId: string) => void;
    onOpenDrug?: (drugId: string) => void;
    onOpenTarget?: (targetId: string) => void;
    onOpenDisease?: (diseaseId: string) => void;
    onOpenOrganization?: (organizationId: string) => void;
  } = {},
) {
  const onOpenEntity = callbacks.onOpenEntity ?? vi.fn();
  const onOpenDrug = callbacks.onOpenDrug;
  const onOpenTarget = callbacks.onOpenTarget;
  const onOpenDisease = callbacks.onOpenDisease;
  const onOpenOrganization = callbacks.onOpenOrganization;
  const onOpenEpidemiology = vi.fn();
  function Harness() {
    const [activeSection, setActiveSection] = useState(initialSection);
    return (
      <DiseaseView
        disease={entity}
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        onOpenEpidemiology={onOpenEpidemiology}
        onOpenEntity={onOpenEntity}
        onOpenDrug={onOpenDrug}
        onOpenTarget={onOpenTarget}
        onOpenDisease={onOpenDisease}
        onOpenOrganization={onOpenOrganization}
        onOpenTrial={vi.fn()}
        onOpenPatent={vi.fn()}
        onOpenDeal={vi.fn()}
        onOpenRegulatoryEvent={vi.fn()}
        onOpenNewsEvent={vi.fn()}
      />
    );
  }
  return { ...renderWithQueryClient(<Harness />), onOpenEntity, onOpenEpidemiology };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(loadDiseaseDossier).mockResolvedValue(dossier);
});

it.each([0, 1])("counts the separately rendered epidemiology domain in coverage: %s records", async (total) => {
  vi.mocked(loadDiseaseDossier).mockResolvedValueOnce({
    ...dossier,
    coverage: dossier.coverage.map((item) => ({ ...item, total: 0, returned: 0, status: "not_observed" as const })),
    epidemiology: { ...dossier.epidemiology, total, items: total ? dossier.epidemiology.items : [] },
  });
  renderDiseaseView();
  const summary = await screen.findByText(`${total} / ${dossier.coverage.length + 1} 个信息领域有记录`);
  if (total) expect(summary.closest("details")).toHaveAttribute("open");
  else expect(summary.closest("details")).not.toHaveAttribute("open");
});

it("renders a governed disease landscape and cross-domain professional sections", async () => {
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenTarget = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  const { onOpenEpidemiology } = renderDiseaseView(disease, "overview", {
    onOpenEntity,
    onOpenDrug,
    onOpenTarget,
    onOpenDisease,
    onOpenOrganization,
  });

  expect(await screen.findByRole("heading", { name: disease.name })).toBeInTheDocument();
  expect(loadDiseaseDossier).toHaveBeenCalledWith(disease.id, expect.any(AbortSignal));
  expect(screen.queryAllByText(/已确认|已查证/)).toHaveLength(0);
  expect(screen.queryByText("规范靶点实体")).not.toBeInTheDocument();
  expect(screen.getAllByText("II 期临床")).toHaveLength(2);
  expect(screen.getByRole("table", { name: "最新疾病负担观测" })).toHaveTextContent("158,000");

  fireEvent.click(screen.getByRole("button", { name: "EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("target-1");
  expect(onOpenEntity).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "进入流行病学数据库" }));
  expect(onOpenEpidemiology).toHaveBeenCalledWith(disease.id);

  fireEvent.click(screen.getByRole("tab", { name: "流行病学" }));
  expect(screen.getByRole("table", { name: "疾病流行病学观测" })).toHaveTextContent("National Registry");
  fireEvent.click(screen.getByRole("button", { name: "National Registry" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("publisher-1");
  fireEvent.click(screen.getByRole("tab", { name: "研发格局" }));
  fireEvent.click(screen.getByRole("button", { name: "VX-201" }));
  fireEvent.click(screen.getByRole("button", { name: "Victor Oncology" }));
  fireEvent.click(screen.getByRole("button", { name: disease.name }));
  expect(onOpenDrug).toHaveBeenCalledWith("drug-1");
  expect(onOpenOrganization).toHaveBeenCalledWith("company-1");
  expect(onOpenDisease).toHaveBeenCalledWith(disease.id);
  fireEvent.click(screen.getByRole("tab", { name: "靶点证据" }));
  expect(screen.getByRole("table", { name: "疾病关联靶点证据" })).toHaveTextContent("EGFR cohort study");
  fireEvent.click(screen.getByRole("button", { name: "EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("target-1");
});

it("uses public product copy when a disease summary is unavailable", async () => {
  vi.mocked(loadDiseaseDossier).mockResolvedValueOnce({
    ...dossier,
    entity: { ...dossier.entity, description: null },
  });
  renderDiseaseView(disease);

  expect(await screen.findByText("暂无疾病简介")).toBeInTheDocument();
  expect(screen.queryByText("暂无经治理的疾病摘要")).not.toBeInTheDocument();
});

it("presents a provider condition as a registry label, not a canonical disease landscape", async () => {
  const registryLabel: Entity = {
    ...disease,
    name: "Abemaciclib",
    description: null,
    external_ids: {},
    attributes: {
      identity_scope: "provider_label",
      label_provider: "ClinicalTrials.gov",
      identity_note: "ClinicalTrials.gov研究条件名称，不代表获批适应症或本体标准化。",
    },
  };
  vi.mocked(loadDiseaseDossier).mockResolvedValueOnce({
    ...dossier,
    entity: {
      ...dossier.entity,
      name: registryLabel.name,
      description: registryLabel.description,
      external_ids: registryLabel.external_ids,
      attributes: registryLabel.attributes,
      canonical_entity_id: registryLabel.id,
    },
  });
  renderDiseaseView(registryLabel);

  expect(await screen.findByText("登记条件档案")).toBeInTheDocument();
  expect(screen.getByRole("note", { name: "来源名称范围" })).toHaveTextContent("不代表获批适应症或本体标准化");
  expect(screen.queryByText("疾病专业档案")).not.toBeInTheDocument();
  expect(screen.queryByText("最高研发阶段")).not.toBeInTheDocument();
  expect(screen.queryByRole("table", { name: "最新疾病负担观测" })).not.toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "关联试验" })).toBeInTheDocument();
});

it("renders a recoverable disease dossier error", async () => {
  vi.mocked(loadDiseaseDossier).mockRejectedValueOnce(new Error("Disease service unavailable"));
  renderDiseaseView();
  expect(await screen.findByText("Disease service unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
});

it("fails closed for a non-disease deep link", () => {
  renderDiseaseView({ ...disease, entity_type: "drug", name: "VX-201" });
  expect(screen.getByText("该深链接不是疾病实体，无法打开疾病专业档案")).toBeInTheDocument();
  expect(loadDiseaseDossier).not.toHaveBeenCalled();
});
