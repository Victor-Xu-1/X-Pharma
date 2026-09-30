import { fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { type DiseaseDossier, loadDiseaseDossier } from "../lib/contracts/disease";
import type { Entity } from "../lib/types";
import type { DiseaseDossierSection } from "../lib/workspaceRouting";
import { DiseaseView } from "../views/DiseaseView";
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

const disease: Entity = {
  id: "disease-1",
  canonical_entity_id: "disease-1",
  entity_type: "disease",
  name: "EGFR 阳性非小细胞肺癌",
  description: "经治理的疾病定义与生物标志物人群",
  external_ids: { mesh: "D002289" },
  attributes: { biomarker: "EGFR-positive" },
  review_status: "verified",
  created_at: "2026-07-20T08:00:00Z",
  updated_at: "2026-07-25T08:00:00Z",
};

const dossier: DiseaseDossier = {
  entity: {
    ...disease,
    canonical_entity_id: disease.id,
    identity_identifiers: [],
    review_status: "verified",
  },
  summary: {
    program_count: 1,
    drug_count: 1,
    target_count: 1,
    organization_count: 1,
    clinical_trial_count: 0,
    patent_count: 0,
    epidemiology_observation_count: 1,
    patient_population_count: 1,
    modalities: ["small molecule"],
    phase_distribution: { phase_2: 1 },
    highest_phase: "phase_2",
    measures: ["prevalence"],
    geographies: ["China"],
    latest_activity_at: "2026-07-24T00:00:00Z",
  },
  epidemiology: {
    items: [
      {
        id: "observation-1",
        observation_identifier: "EPI-EGFR-CN-2025",
        disease_entity_id: disease.id,
        patient_population_id: "population-1",
        measure: "prevalence",
        value: 158000,
        lower_bound: 150000,
        upper_bound: 166000,
        unit: "patients",
        geography: "China",
        population_scope: "adults",
        age_group: "18+",
        sex: "all",
        period_start: "2025-01-01T00:00:00Z",
        period_end: "2025-12-31T00:00:00Z",
        sample_size: 12500,
        methodology: "Registry-calibrated prevalence model",
        publisher_entity_id: "publisher-1",
        source_document_id: "source-1",
        disease_entity: { id: disease.id, name: disease.name, entity_type: "disease" },
        publisher_entity: { id: "publisher-1", name: "National Registry", entity_type: "organization" },
        patient_population: {
          id: "population-1",
          population_key: "egfr-nsclc-cn",
          name: "中国 EGFR 阳性 NSCLC 患者",
          description: null,
          attributes: {},
          disease_entities: [{ id: disease.id, name: disease.name, entity_type: "disease" }],
          target_entities: [{ id: "target-1", name: "EGFR", entity_type: "target" }],
        },
      },
    ],
    total: 1,
    limit: 100,
    offset: 0,
    facets: { measure: { prevalence: 1 }, geography: { China: 1 } },
    patient_populations: [{ id: "population-1", name: "中国 EGFR 阳性 NSCLC 患者", count: 1 }],
    landscape: {
      total_observations: 1,
      measure: [{ key: "prevalence", label: "prevalence", count: 1, share: 1 }],
      geography: [{ key: "China", label: "China", count: 1, share: 1 }],
      population_scope: [{ key: "adults", label: "adults", count: 1, share: 1 }],
    },
    as_of: "2026-07-25T12:00:00Z",
    query_schema_version: "pharma.epidemiology.search.v3",
    sort_by: "period_end",
    sort_direction: "desc",
    applied_filters: [{ field: "disease_entity_id", operator: "eq", value: disease.id }],
    warnings: ["观测值受统计口径与授权来源限制。"],
  },
  programs: [
    {
      id: "program-1",
      drug_entity_id: "drug-1",
      drug_name: "VX-201",
      target_entity_id: "target-1",
      target_name: "EGFR",
      targets: [{ entity_id: "target-1", name: "EGFR", position: 0, role: "primary" }],
      disease_entity_id: disease.id,
      disease_name: disease.name,
      organization_entity_id: "company-1",
      organization_name: "Victor Oncology",
      modality: "small molecule",
      mechanism_of_action: "EGFR inhibitor",
      phase: "phase_2",
      status_date: "2026-07-24T00:00:00Z",
      status_detail: "active",
      geography: "global",
      source_document_id: "source-1",
    },
  ],
  target_evidence: [
    {
      id: "evidence-1",
      target_entity_id: "target-1",
      target_name: "EGFR",
      disease_entity_id: disease.id,
      disease_name: disease.name,
      evidence_type: "genetic_association",
      direction: "supports",
      study_name: "EGFR cohort study",
      population: "East Asian adults",
      effect_size: 2.4,
      effect_unit: "OR",
      p_value: 0.0001,
      sample_size: 8000,
      summary: "EGFR mutation supports biomarker-defined disease stratification.",
      observed_at: "2026-06-01T00:00:00Z",
      source_system: "curated_registry",
      source_record_id: "record-1",
    },
  ],
  relationships: [],
  activities: [],
  clinical_trials: [],
  patents: [],
  deals: [],
  regulatory_events: [],
  news_events: [],
  structures: [],
  coverage: [
    { domain: "programs", total: 1, returned: 1, status: "available", note: "已返回全部管线" },
    { domain: "target_evidence", total: 1, returned: 1, status: "available", note: "已返回全部证据" },
  ],
  as_of: "2026-07-25T12:00:00Z",
  warnings: ["未观察到记录不代表不存在相关活动。"],
};

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
