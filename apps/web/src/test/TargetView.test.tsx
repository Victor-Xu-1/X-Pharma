import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import {
  emptyPipelineSearchFilters,
  type PipelineAnalysisDimension,
  type PipelineAnalysisLimit,
  type PipelineAnalysisStageScope,
  type PipelineAnalysisView,
  type PipelineTargetAggregation,
  searchPipelines,
} from "../lib/contracts/pipeline";
import { loadRecordProvenance } from "../lib/contracts/provenance";
import { loadTargetDossier, loadTargetSar } from "../lib/contracts/target";
import type { Entity } from "../lib/types";
import type { TargetDossierSection } from "../lib/workspaceRouting";
import { TargetView } from "../views/TargetView";
import { pipelineProgramStatusLabel, pipelineSelectOptions } from "../views/target/pipeline/presentation";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/target", () => ({
  targetKeys: {
    dossier: (targetId: string) => ["target", targetId, "dossier"],
    sar: (targetId: string, filters: unknown) => ["target", targetId, "sar", filters],
  },
  loadTargetDossier: vi.fn(),
  loadTargetSar: vi.fn(),
}));

vi.mock("../lib/contracts/pipeline", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/contracts/pipeline")>();
  return {
    ...original,
    searchPipelines: vi.fn(),
  };
});

vi.mock("../lib/contracts/provenance", () => ({
  provenanceKeys: {
    record: (resourceType: string, resourceId: string) => ["provenance", resourceType, resourceId],
  },
  loadRecordProvenance: vi.fn(),
}));

const target: Entity = {
  id: "target-1",
  canonical_entity_id: "target-1",
  entity_type: "target",
  name: "EGFR",
  description: "Epidermal growth factor receptor",
  external_ids: { uniprot: "P00533" },
  attributes: {},
  review_status: "verified",
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T11:00:00Z",
};

type TargetPipelineAnalysisState = {
  dimension: PipelineAnalysisDimension;
  view: PipelineAnalysisView;
  limit: PipelineAnalysisLimit;
  stageScope: PipelineAnalysisStageScope;
  targetAggregation: PipelineTargetAggregation;
};

function renderTargetView({
  onOpenEntity = vi.fn(),
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
  onOpenPatent = vi.fn(),
  onOpenDeal = vi.fn(),
  onOpenRegulatoryEvent = vi.fn(),
  onOpenNewsEvent = vi.fn(),
  onOpenEvidence = vi.fn(),
  onPipelineSearchChange = vi.fn(),
  onPipelineLandscapeFilterApply,
  onPipelineDisplayModeChange = vi.fn(),
  onPipelineAnalysisChange = vi.fn(),
  initialPipelineFilters,
  initialPipelineDisplayMode,
  initialPipelineAnalysis,
  initialSection = "overview",
}: {
  onOpenEntity?: (entityId: string) => void;
  onOpenDrug?: (drugId: string) => void;
  onOpenTarget?: (targetId: string) => void;
  onOpenDisease?: (diseaseId: string) => void;
  onOpenOrganization?: (organizationId: string) => void;
  onOpenPatent?: (patentId: string) => void;
  onOpenDeal?: (dealId: string) => void;
  onOpenRegulatoryEvent?: (eventId: string) => void;
  onOpenNewsEvent?: (eventId: string) => void;
  onOpenEvidence?: (query: string) => void;
  onPipelineSearchChange?: (filters: Parameters<typeof searchPipelines>[0]) => void;
  onPipelineLandscapeFilterApply?: (
    filters: Parameters<typeof searchPipelines>[0],
    displayMode: "drug" | "program" | "landscape",
  ) => void;
  onPipelineDisplayModeChange?: (displayMode: "drug" | "program" | "landscape") => void;
  onPipelineAnalysisChange?: (analysis: TargetPipelineAnalysisState) => void;
  initialPipelineFilters?: Parameters<typeof searchPipelines>[0];
  initialPipelineDisplayMode?: "drug" | "program" | "landscape";
  initialPipelineAnalysis?: TargetPipelineAnalysisState;
  initialSection?: TargetDossierSection;
} = {}) {
  function Harness() {
    const [activeSection, setActiveSection] = useState<TargetDossierSection>(initialSection);
    return (
      <TargetView
        target={target}
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        onOpenEntity={onOpenEntity}
        onOpenDrug={onOpenDrug}
        onOpenTarget={onOpenTarget}
        onOpenDisease={onOpenDisease}
        onOpenOrganization={onOpenOrganization}
        onOpenTrial={vi.fn()}
        onOpenPatent={onOpenPatent}
        onOpenDeal={onOpenDeal}
        onOpenRegulatoryEvent={onOpenRegulatoryEvent}
        onOpenNewsEvent={onOpenNewsEvent}
        onOpenEvidence={onOpenEvidence}
        initialPipelineFilters={initialPipelineFilters}
        onPipelineSearchChange={onPipelineSearchChange}
        onPipelineLandscapeFilterApply={onPipelineLandscapeFilterApply}
        initialPipelineDisplayMode={initialPipelineDisplayMode}
        onPipelineDisplayModeChange={onPipelineDisplayModeChange}
        initialPipelineAnalysis={initialPipelineAnalysis}
        onPipelineAnalysisChange={onPipelineAnalysisChange}
      />
    );
  }

  return renderWithQueryClient(<Harness />);
}

beforeEach(() => {
  vi.mocked(searchPipelines).mockResolvedValue({
    items: [
      {
        id: "program-1",
        drug_entity_id: "drug-1",
        drug_name: "Compound A",
        disease_entity_id: "disease-1",
        disease_name: "非小细胞肺癌",
        geography: "global",
        mechanism_of_action: "EGFR inhibitor",
        modality: "small molecule",
        organization_entity_id: "organization-1",
        organization_name: "Acme Pharma",
        phase: "phase_2",
        source_document_id: "document-1",
        status_date: "2026-07-18T00:00:00Z",
        status_detail: null,
        target_entity_id: target.id,
        target_name: target.name,
        program_status: "active",
        clinical_trial_count: 3,
        deal_count: 1,
        project_count: 2,
        targets: [{ entity_id: target.id, name: target.name, role: "primary", position: 0 }],
        organizations: [
          {
            entity_id: "organization-1",
            name: "Acme Pharma",
            role: "originator",
            position: 0,
          },
        ],
        indications: [
          {
            program_id: "program-1",
            disease_entity_id: "disease-1",
            disease_name: "非小细胞肺癌",
            phase: "phase_2",
            global_phase: "phase_2",
            program_status: "active",
            status_date: "2026-07-18T00:00:00Z",
            geography: "global",
          },
        ],
        modalities: ["small molecule"],
        mechanisms_of_action: ["EGFR inhibitor"],
        innovation_types: ["First-in-Class"],
        therapeutic_areas: ["肿瘤领域"],
        program_status_counts: { active: 2 },
      },
    ],
    total: 1048,
    project_total: 1165,
    result_grain: "drug",
    limit: 20,
    offset: 0,
    sort_by: "status_date",
    sort_direction: "desc",
    sort: [{ field: "status_date", direction: "desc" }],
    query_schema_version: "pharma.pipeline.search.v13",
    applied_filters: [{ field: "target_entity_id", operator: "eq", value: target.id }],
    facets: {
      modality: { "small molecule": 812, antibody: 31 },
      innovation_type: { "First-in-Class": 63 },
      therapeutic_area: { 肿瘤领域: 1102 },
      drug_category: { 化学药品: 795 },
      phase: { approved: 97, phase_3: 84, phase_2: 305 },
      geography: { global: 1001 },
      global_phase: { approved: 97, phase_3: 84, phase_2: 305 },
      china_phase: { approved: 21, phase_3: 46, phase_2: 188 },
      program_status: { active: 987, inactive: 144, unknown: 34 },
      organization_role: { originator: 1048 },
      organization_type: { biopharma: 311 },
      organization_country_region: { US: 207 },
      development_rights_region: { Global: 886 },
      commercialization_rights_region: { China: 372 },
      program_tag: { first_in_class: 63 },
      milestone_type: { first_patient_in: 221 },
      has_clinical_results: { true: 427, false: 738 },
      clinical_result_evaluation: { positive: 205 },
      has_deal: { true: 183, false: 982 },
      deal_currency: { USD: 172 },
    },
    landscape: {
      total_programs: 1165,
      distinct_drugs: 1048,
      distinct_targets: 1,
      distinct_diseases: 134,
      distinct_organizations: 311,
      limit: 20,
      stage_scope: "overall",
      target_aggregation: "all",
      diseases: [
        {
          key: "disease-1",
          label: "非小细胞肺癌",
          count: 78,
          share: 0.066953,
          entity_id: "disease-1",
        },
      ],
      target_combinations: [
        {
          key: "target-1|target-2",
          label: "EGFR + MET",
          count: 12,
          share: 0.0103,
          phase_counts: { phase_2: 12 },
        },
      ],
    },
    as_of: "2026-07-18T11:00:00Z",
    warnings: [],
  });
  vi.mocked(loadTargetSar).mockResolvedValue({
    items: [
      {
        id: "77777777-7777-4777-8777-777777777777",
        compound_entity_id: "compound-1",
        compound_name: "VX-101",
        target_entity_id: target.id,
        assay_id: "assay-1",
        assay_type: "binding",
        assay_format: "biochemical",
        organism: "Homo sapiens",
        cell_line: null,
        standard_type: "IC50",
        standard_relation: "=",
        standard_value: 12,
        standard_units: "nM",
        pchembl_value: 7.92,
        comparison_group:
          "standard_type=IC50|assay_type=binding|assay_format=biochemical|organism=Homo sapiens|cell_line=unspecified",
        comparable: true,
        comparability_reasons: [],
        potency_rank: 1,
        delta_pchembl: 0,
        canonical_smiles: null,
        standard_inchi_key: "ABCDEFGHIJKLMN-ABCDEFGHIJ-A",
        validity_comment: null,
        source_system: "governed_ai",
        source_activity_id: "activity-1",
        source_document_id: "44444444-4444-4444-8444-444444444444",
      },
      {
        id: "88888888-8888-4888-8888-888888888888",
        compound_entity_id: "compound-2",
        compound_name: "VX-102",
        target_entity_id: target.id,
        assay_id: "assay-2",
        assay_type: null,
        assay_format: null,
        organism: null,
        cell_line: null,
        standard_type: "IC50",
        standard_relation: "<",
        standard_value: 100,
        standard_units: "nM",
        pchembl_value: 7,
        comparison_group:
          "standard_type=IC50|assay_type=unspecified|assay_format=unspecified|organism=unspecified|cell_line=unspecified",
        comparable: false,
        comparability_reasons: ["censored_or_approximate_relation", "assay_type_missing", "assay_format_missing"],
        source_system: "governed_ai",
        source_activity_id: "activity-2",
      },
    ],
    total: 2,
    limit: 50,
    offset: 0,
    facets: {
      standard_type: { IC50: 2 },
      assay_type: { binding: 1 },
      assay_format: { biochemical: 1 },
      organism: { "Homo sapiens": 1 },
      cell_line: {},
    },
    as_of: "2026-07-21T00:00:00Z",
    warnings: ["仅在相同 Assay 上下文内比较。"],
  });
  vi.mocked(loadTargetDossier).mockResolvedValue({
    entity: {
      ...target,
      canonical_entity_id: target.id,
      identity_identifiers: [],
      review_status: "verified",
    },
    profile: {
      activity_count: 0,
      as_of: "2026-07-18T11:00:00Z",
      entity: {
        id: target.id,
        canonical_entity_id: "target-1",
        entity_type: "target",
        name: target.name,
        description: target.description,
        external_ids: target.external_ids,
        attributes: target.attributes,
        review_status: "verified",
        created_at: target.created_at,
        updated_at: target.updated_at,
      },
      function_summary: "Governed EGFR summary",
      gene_symbol: "EGFR",
      organism: "Homo sapiens",
      program_count: 0,
      target_class: "SINGLE PROTEIN",
      uniprot_accession: "P00533",
    },
    activities: [],
    relationships: [],
    programs: [],
    clinical_trials: [],
    patents: [],
    deals: [],
    regulatory_events: [],
    news_events: [],
    structures: [],
    target_evidence: [
      {
        id: "66666666-6666-4666-8666-666666666666",
        source_system: "governed_ai",
        source_record_id: "egfr-gwas-1",
        target_entity_id: target.id,
        target_name: target.name,
        disease_entity_id: "disease-1",
        disease_name: "非小细胞肺癌",
        evidence_type: "genetic_association",
        direction: "supports",
        study_name: "EGFR NSCLC GWAS",
        population: "East Asian",
        variant: "rs121434568",
        effect_size: 1.8,
        effect_unit: "odds ratio",
        p_value: 1.2e-8,
        sample_size: 12000,
        summary: "遗传关联支持 EGFR 靶点假设",
        observed_at: "2026-07-21T00:00:00Z",
        qualifiers: {},
        source_document_id: "44444444-4444-4444-8444-444444444444",
      },
    ],
    coverage: [
      { domain: "evidence", total: 1, returned: 1, status: "available", note: "internal evidence route" },
      { domain: "target_evidence", total: 1, returned: 1, status: "available", note: "已返回当前匹配记录" },
      { domain: "activities", total: 0, returned: 0, status: "not_observed", note: "当前未观察到" },
    ],
    summary: {
      program_count: 0,
      phase_distribution: { phase_2: 25, approved: 24, phase_3: 19, phase_1: 12 },
      highest_phase: null,
      clinical_trial_count: 0,
      recruiting_trial_count: 0,
      unclassified_trial_status_count: 0,
      patent_count: 0,
      active_patent_count: 0,
      unclassified_patent_status_count: 0,
      regulatory_event_count: 0,
      approval_event_count: 0,
      status_vocabulary_version: "target-dossier-status@1",
    },
    as_of: "2026-07-18T11:00:00Z",
    warnings: [],
  });
  vi.mocked(loadRecordProvenance).mockResolvedValue({
    resource_type: "activity_measurement",
    resource_id: "11111111-1111-4111-8111-111111111111",
    items: [
      {
        id: "22222222-2222-4222-8222-222222222222",
        resource_type: "activity_measurement",
        resource_id: "11111111-1111-4111-8111-111111111111",
        dataset_key: "literature",
        evidence_claim_id: "33333333-3333-4333-8333-333333333333",
        source_document_id: "44444444-4444-4444-8444-444444444444",
        source_version_id: "55555555-5555-4555-8555-555555555555",
        content_sha256: "a".repeat(64),
        document_name: "EGFR evidence",
        source_uri: "https://example.test/egfr",
        locator: "page=7;paragraph=2",
        quote: "EGFR activity was 12 nM.",
        subject_entity_id: target.id,
        review_status: "verified",
        created_at: "2026-07-19T10:00:00Z",
        license: { attribution: "Licensed evidence" },
        warnings: [],
      },
    ],
    license_scopes: [],
    warnings: [],
  });
});

it("presents linked trial phases and recruitment states in novice-friendly Chinese", async () => {
  const dossierImplementation = vi.mocked(loadTargetDossier).getMockImplementation();
  if (!dossierImplementation) throw new Error("target dossier fixture is not configured");
  const dossier = await dossierImplementation("target-1");
  vi.mocked(loadTargetDossier).mockClear();
  const trial: (typeof dossier.clinical_trials)[number] = {
    acronym: "TARGET-D 203",
    arms: [],
    completion_date: null,
    completion_date_precision: null,
    conditions: ["结直肠癌", "胰腺癌", "非小细胞肺癌", "头颈部鳞癌", "胃癌"],
    eligibility: {
      criteria: null,
      gender_based: null,
      healthy_volunteers: null,
      maximum_age: null,
      minimum_age: null,
      sampling_method: null,
      sex: null,
    },
    enrollment: 150,
    entity_id: "trial-entity-1",
    has_results: false,
    id: "trial-1",
    initiation_type: "ist",
    interventions: [],
    last_update_posted: "2026-07-18T00:00:00Z",
    linked_entities: [],
    locations: [],
    official_title: "TARGET-D 203",
    outcomes: [],
    overall_status: "RECRUITING",
    phases: ["PHASE2"],
    registry_id: "NCT07659795",
    registry_name: "ClinicalTrials.gov",
    result_evaluation: null,
    results_first_posted: null,
    source_document_id: null,
    sponsors: [],
    start_date: "2026-01-01",
    start_date_precision: "day",
    status_history: [],
    study_design: {
      allocation: null,
      intervention_model: null,
      intervention_model_description: null,
      masking: null,
      masking_description: null,
      observational_model: null,
      primary_purpose: null,
      time_perspective: null,
      who_masked: [],
    },
    study_type: "INTERVENTIONAL",
    therapy_lines: [],
  };
  vi.mocked(loadTargetDossier).mockResolvedValueOnce({
    ...dossier,
    clinical_trials: Array.from({ length: 12 }, (_, index) => ({
      ...trial,
      id: `trial-${index + 1}`,
      entity_id: `trial-entity-${index + 1}`,
      registry_id: index === 0 ? trial.registry_id : `NCT-DEMO-${index + 1}`,
      official_title: index === 0 ? trial.official_title : `EGFR trial ${index + 1}`,
      conditions: index === 0 ? [...trial.conditions] : [`适应症 ${index + 1}`],
    })),
  });

  renderTargetView({ initialSection: "trials" });

  expect(await screen.findByText("NCT07659795 · II 期")).toBeInTheDocument();
  expect(screen.getAllByText("招募中")).toHaveLength(10);
  expect(screen.queryByText("RECRUITING")).not.toBeInTheDocument();
  expect(screen.queryByText("PHASE2")).not.toBeInTheDocument();
  expect(screen.getByText("当前显示 10 / 共 12 项临床试验")).toBeInTheDocument();
  expect(screen.getAllByRole("article")).toHaveLength(10);
  expect(screen.queryByRole("heading", { name: "EGFR trial 11" })).not.toBeInTheDocument();
  expect(screen.getByText(/结直肠癌、胰腺癌、非小细胞肺癌/)).toBeInTheDocument();
  expect(screen.queryByText(/头颈部鳞癌/)).not.toBeInTheDocument();
  const allConditionsButton = screen.getByRole("button", { name: "查看全部 5 项适应症" });
  expect(allConditionsButton).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(allConditionsButton);
  expect(screen.getByText(/头颈部鳞癌、胃癌/)).toBeInTheDocument();
  const collapseConditionsButton = screen.getByRole("button", { name: "收起适应症" });
  expect(collapseConditionsButton).toHaveAttribute("aria-expanded", "true");
  fireEvent.click(collapseConditionsButton);
  expect(screen.queryByText(/头颈部鳞癌/)).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "继续显示 2 项" }));
  expect(screen.getAllByRole("article")).toHaveLength(12);
  expect(screen.getByRole("heading", { name: "EGFR trial 11" })).toBeInTheDocument();
  expect(screen.getByText("当前显示 12 / 共 12 项临床试验")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "收起至前 10 项" }));
  expect(screen.getAllByRole("article")).toHaveLength(10);
  expect(screen.queryByRole("heading", { name: "EGFR trial 11" })).not.toBeInTheDocument();
});

it("loads the governed dossier through one cancellable query and follows controlled tab state", async () => {
  const onOpenEvidence = vi.fn();
  renderTargetView({ onOpenEvidence });

  expect(await screen.findByRole("heading", { name: "EGFR" })).toBeInTheDocument();
  expect(screen.getByText("Epidermal growth factor receptor")).toBeInTheDocument();
  expect(screen.getByText("单蛋白 · 人")).toBeInTheDocument();
  expect(screen.queryByText(/SINGLE PROTEIN/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Homo sapiens/)).not.toBeInTheDocument();
  expect(loadTargetDossier).toHaveBeenCalledWith("target-1", expect.any(AbortSignal));
  expect(screen.getByText("Governed EGFR summary")).toBeInTheDocument();
  expect(screen.getByText("II 期")).toBeInTheDocument();
  expect(screen.getByText("已批准")).toBeInTheDocument();
  expect(screen.getByText("III 期")).toBeInTheDocument();
  expect(screen.getByText("I 期")).toBeInTheDocument();
  expect(screen.queryByText("phase_2")).not.toBeInTheDocument();
  expect(screen.queryAllByText(/已确认|已查证/)).toHaveLength(0);
  expect(screen.getByRole("heading", { name: "关联信息" })).toBeInTheDocument();
  expect(screen.getByText("暂无可展示信息")).toBeInTheDocument();
  expect(screen.queryByText("当前数据源未找到相关记录")).not.toBeInTheDocument();
  expect(screen.queryByText("internal evidence route")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "查看来源证据" }));
  expect(onOpenEvidence).toHaveBeenCalledWith("EGFR");
  fireEvent.click(screen.getByRole("button", { name: "查看转化证据" }));
  expect(screen.getByRole("tab", { name: "转化证据" })).toHaveAttribute("aria-selected", "true");
  fireEvent.click(screen.getByRole("tab", { name: "活性数据" }));
  expect(screen.getByText("暂无活性数据")).toBeInTheDocument();
  expect(screen.getByText("当前可见来源和更新时间范围内没有可展示的活性记录")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "监管动态" }));
  expect(screen.getByText("暂无关联监管事件")).toBeInTheDocument();
  expect(loadTargetDossier).toHaveBeenCalledOnce();
});

it("loads licensed record provenance only after an evidence action and closes on Escape", async () => {
  vi.mocked(loadTargetDossier).mockResolvedValueOnce({
    entity: {
      ...target,
      canonical_entity_id: target.id,
      identity_identifiers: [],
      review_status: "verified",
    },
    profile: {
      activity_count: 1,
      as_of: "2026-07-18T11:00:00Z",
      entity: {
        id: target.id,
        canonical_entity_id: target.id,
        entity_type: target.entity_type,
        name: target.name,
        description: target.description,
        external_ids: target.external_ids,
        attributes: target.attributes,
        review_status: "verified",
        created_at: target.created_at,
        updated_at: target.updated_at,
      },
      function_summary: "Governed EGFR summary",
      gene_symbol: "EGFR",
      organism: "Homo sapiens",
      program_count: 0,
      target_class: "Receptor tyrosine kinase",
      uniprot_accession: "P00533",
    },
    activities: [
      {
        id: "11111111-1111-4111-8111-111111111111",
        compound_entity_id: "compound-1",
        target_entity_id: target.id,
        assay_id: "assay-1",
        standard_type: "IC50",
        standard_relation: "=",
        standard_value: 12,
        standard_units: "nM",
        pchembl_value: 7.92,
        reported_type: "IC50",
        reported_relation: "=",
        reported_value: "12",
        reported_units: "nM",
        source_system: "governance",
        source_activity_id: "activity-1",
        source_document_id: "44444444-4444-4444-8444-444444444444",
      },
    ],
    relationships: [],
    programs: [],
    clinical_trials: [],
    patents: [],
    deals: [],
    regulatory_events: [],
    news_events: [],
    structures: [],
    target_evidence: [],
    coverage: [],
    summary: {
      program_count: 0,
      phase_distribution: {},
      highest_phase: null,
      clinical_trial_count: 0,
      recruiting_trial_count: 0,
      unclassified_trial_status_count: 0,
      patent_count: 0,
      active_patent_count: 0,
      unclassified_patent_status_count: 0,
      regulatory_event_count: 0,
      approval_event_count: 0,
      status_vocabulary_version: "target-dossier-status@1",
    },
    as_of: "2026-07-18T11:00:00Z",
    warnings: [],
  });
  renderTargetView();

  fireEvent.click(await screen.findByRole("tab", { name: "活性数据" }));
  expect(loadRecordProvenance).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "查看 活性记录 的原始证据" }));

  expect(await screen.findByRole("heading", { name: "原始证据" })).toBeInTheDocument();
  expect(await screen.findByText("EGFR activity was 12 nM.")).toBeInTheDocument();
  expect(loadRecordProvenance).toHaveBeenCalledWith(
    {
      resourceType: "activity_measurement",
      resourceId: "11111111-1111-4111-8111-111111111111",
      label: "活性记录",
    },
    expect.any(AbortSignal),
  );

  const closeProvenance = screen.getByRole("button", { name: "关闭原始证据" });
  await waitFor(() => expect(closeProvenance).toHaveFocus());
  fireEvent.keyDown(closeProvenance, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

it("filters translational evidence, opens the linked disease, and requests provenance on demand", async () => {
  const onOpenEntity = vi.fn();
  const onOpenDisease = vi.fn();
  renderTargetView({ onOpenEntity, onOpenDisease });

  fireEvent.click(await screen.findByRole("tab", { name: "转化证据" }));
  expect(screen.getAllByText("遗传关联")).toHaveLength(2);
  expect(screen.getByText("支持靶点假设")).toBeInTheDocument();
  expect(screen.getByText("1 / 1 条")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("证据类型"), { target: { value: "expression" } });
  expect(screen.getByText("当前筛选条件下无匹配证据")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("证据类型"), { target: { value: "genetic_association" } });
  fireEvent.click(screen.getByRole("button", { name: "非小细胞肺癌" }));
  expect(onOpenDisease).toHaveBeenCalledWith("disease-1");
  expect(onOpenEntity).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "查看 遗传关联支持 EGFR 靶点假设 的原始证据" }));
  await waitFor(() =>
    expect(loadRecordProvenance).toHaveBeenCalledWith(
      {
        resourceType: "target_evidence",
        resourceId: "66666666-6666-4666-8666-666666666666",
        label: "遗传关联支持 EGFR 靶点假设",
      },
      expect.any(AbortSignal),
    ),
  );
});

it("opens typed relationship and pipeline entities from the target dossier", async () => {
  const base = await vi.mocked(loadTargetDossier)("template", new AbortController().signal);
  vi.mocked(loadTargetDossier).mockResolvedValue({
    ...base,
    relationships: [
      {
        id: "relationship-1",
        direction: "outgoing",
        predicate: "developed_by",
        related_entity: {
          id: "organization-1",
          canonical_entity_id: "organization-1",
          entity_type: "organization",
          name: "Acme Pharma",
          description: null,
          external_ids: {},
          attributes: {},
          review_status: "verified",
          created_at: "2026-07-18T10:00:00Z",
          updated_at: "2026-07-18T11:00:00Z",
        },
        review_status: "verified",
        attributes: {},
        valid_from: null,
        valid_to: null,
      },
    ],
    programs: [
      {
        id: "program-1",
        drug_entity_id: "drug-1",
        drug_name: "Compound A",
        disease_entity_id: "disease-1",
        disease_name: "非小细胞肺癌",
        geography: "global",
        mechanism_of_action: "EGFR inhibitor",
        modality: "small molecule",
        organization_entity_id: "organization-1",
        organization_name: "Acme Pharma",
        phase: "phase_2",
        source_document_id: "document-1",
        status_date: "2026-07-18T00:00:00Z",
        status_detail: null,
        target_entity_id: target.id,
        target_name: target.name,
      },
    ],
  });
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  renderTargetView({ onOpenEntity, onOpenDrug, onOpenDisease, onOpenOrganization });

  fireEvent.click(await screen.findByRole("tab", { name: "关系网络" }));
  expect(screen.queryByRole("columnheader", { name: "状态" })).not.toBeInTheDocument();
  expect(screen.queryAllByText(/已确认|已查证/)).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Acme Pharma" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("organization-1");

  fireEvent.click(screen.getByRole("tab", { name: "竞品管线" }));
  fireEvent.click(await screen.findByRole("button", { name: "Compound A" }));
  fireEvent.click(screen.getByRole("button", { name: "非小细胞肺癌" }));
  fireEvent.click(screen.getByRole("button", { name: "Acme Pharma" }));
  expect(onOpenDrug).toHaveBeenCalledWith("drug-1");
  expect(onOpenDisease).toHaveBeenCalledWith("disease-1");
  expect(onOpenOrganization).toHaveBeenCalledWith("organization-1");
  expect(onOpenEntity).not.toHaveBeenCalled();
});

it("queries the complete target program set with authoritative facets and pagination", async () => {
  renderTargetView();

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  const summary = await screen.findByRole("region", { name: "EGFR 研发药物概览" });
  expect(vi.mocked(searchPipelines).mock.calls[0]?.[0]).toEqual(
    expect.objectContaining({ targetEntityId: target.id, programStatus: "" }),
  );
  expect(summary).toHaveTextContent("1,165 个研发项目");
  expect(summary).toHaveTextContent("1,048 个药物");
  expect(
    screen.getByText(/当前显示 1-1 .*默认按药物汇总全部匹配适应症；可切换项目明细查看每条研发记录。/),
  ).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "结果覆盖范围" })).toHaveTextContent(
    "关联适应症 134 个 · 研发机构 311 家 · 临床结果 427 条 · 交易披露 183 条",
  );
  expect(screen.getByRole("columnheader", { name: "药物" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "适应症与阶段" })).toBeInTheDocument();
  expect(screen.getAllByText("小分子")).toHaveLength(2);
  expect(screen.queryByText("small molecule、INHIBITOR")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "非小细胞肺癌" })).toBeVisible();
  expect(screen.getByText(/2 个研发项目/)).toBeInTheDocument();
  expect(screen.getByText("（原研方）")).toBeInTheDocument();
  expect(screen.getByText("在研", { selector: ".status-badge" })).toBeInTheDocument();
  expect(screen.queryByText("originator")).not.toBeInTheDocument();
  expect(screen.getByRole("option", { name: "在研 (987)" })).toBeInTheDocument();
  const initialSearchResult = vi.mocked(searchPipelines).mock.results[0]?.value;
  if (!initialSearchResult) throw new Error("Missing initial pipeline search result");
  const baselinePipelineResult = (await initialSearchResult) as Awaited<ReturnType<typeof searchPipelines>>;
  const baselineModalityFacets = baselinePipelineResult.facets?.modality ?? {};
  vi.mocked(searchPipelines).mockImplementation(async (nextFilters) => ({
    ...baselinePipelineResult,
    facets: {
      ...baselinePipelineResult.facets,
      modality: nextFilters.modalities.length
        ? Object.fromEntries(nextFilters.modalities.map((value) => [value, baselineModalityFacets[value] ?? 0]))
        : baselineModalityFacets,
    },
  }));
  const modalitySummary = screen.getByRole("group", { name: "药物类型" }).querySelector("summary");
  const findFacetInput = (fieldset: Element | null, label: string) =>
    Array.from(fieldset?.querySelectorAll("label") ?? [])
      .find((option) => option.textContent?.includes(label))
      ?.querySelector("input");
  const requireFacetInput = (fieldset: Element | null, label: string) => {
    const input = findFacetInput(fieldset, label);
    if (!input) throw new Error(`Missing facet input: ${label}`);
    return input;
  };
  if (!modalitySummary) throw new Error("Missing modality facet summary");
  fireEvent.click(modalitySummary);
  const modalityFieldset = modalitySummary.closest("fieldset");
  const smallMoleculeInput = requireFacetInput(modalityFieldset, "小分子");
  fireEvent.click(smallMoleculeInput);
  const updatedAntibodyInput = await waitFor(() => {
    const updatedModalityFieldset =
      screen.getByRole("group", { name: "药物类型" }).querySelector("summary")?.closest("fieldset") ?? null;
    return requireFacetInput(updatedModalityFieldset, "抗体");
  });
  fireEvent.click(updatedAntibodyInput);
  await waitFor(() =>
    expect(searchPipelines).toHaveBeenLastCalledWith(
      expect.objectContaining({ targetEntityId: target.id, modalities: ["small molecule", "antibody"], offset: 0 }),
      { limit: 20, stageScope: "overall", targetAggregation: "all" },
      expect.any(AbortSignal),
      "drug",
    ),
  );
  fireEvent.click(await screen.findByText("更多筛选"));
  expect(screen.getByRole("combobox", { name: "研发机构筛选" })).toHaveAttribute(
    "placeholder",
    "输入至少 2 个字符查找机构",
  );
  expect(screen.getByRole("combobox", { name: "机构标签" })).toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: "机构类型" })).not.toBeInTheDocument();
  const innovationSummary = screen.getByRole("group", { name: "创新类型" }).querySelector("summary");
  if (!innovationSummary) throw new Error("Missing innovation facet summary");
  fireEvent.click(innovationSummary);
  const innovationInput = requireFacetInput(innovationSummary.closest("fieldset"), "First-in-Class");
  fireEvent.click(innovationInput);
  await waitFor(() =>
    expect(searchPipelines).toHaveBeenLastCalledWith(
      expect.objectContaining({ targetEntityId: target.id, innovationTypes: ["First-in-Class"], offset: 0 }),
      { limit: 20, stageScope: "overall", targetAggregation: "all" },
      expect.any(AbortSignal),
      "drug",
    ),
  );
  const updatedInnovationGroup = await screen.findByRole("group", { name: "创新类型" });
  expect(updatedInnovationGroup.querySelector("summary")).toHaveTextContent("First-in-Class");
  const advancedPanel = screen.getByText("更多筛选").closest("details");
  expect(advancedPanel).not.toBeNull();
  expect(advancedPanel).toHaveAttribute("open");
  fireEvent.click(screen.getByText("更多筛选"));
  await waitFor(() => expect(advancedPanel).not.toHaveAttribute("open"));
  fireEvent.click(screen.getByText("列"));
  fireEvent.click(screen.getByRole("checkbox", { name: "显示列：临床结果" }));
  expect(screen.queryByRole("columnheader", { name: "临床结果" })).not.toBeInTheDocument();
  const columnsSummary = screen.getByText("列");
  const resultColumn = screen.getByRole("checkbox", { name: "显示列：临床结果" });
  resultColumn.focus();
  fireEvent.keyDown(resultColumn, { key: "Escape" });
  expect(columnsSummary.closest("details")).not.toHaveAttribute("open");
  expect(columnsSummary).toHaveFocus();
  fireEvent.click(columnsSummary);
  expect(screen.getByRole("checkbox", { name: "显示列：临床结果" })).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "恢复默认列" }));
  expect(screen.getByRole("columnheader", { name: "临床结果" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "加入列表" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "选择本页" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "选择本页" }));
  expect(screen.getByRole("button", { name: "取消选择本页" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "加入列表（1）" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "清空选择" }));
  expect(screen.getByRole("button", { name: "加入列表" })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: "选择对比 Compound A" }));
  expect(screen.getByRole("button", { name: "加入列表（1）" })).toBeEnabled();
  fireEvent.click(await screen.findByRole("button", { name: "可视化" }));
  expect(screen.getByRole("region", { name: "管线竞争格局" })).toBeInTheDocument();
  expect(screen.getByText("1048")).toBeInTheDocument();
  fireEvent.click(screen.getByTitle("按非小细胞肺癌筛选"));
  await waitFor(() =>
    expect(searchPipelines).toHaveBeenLastCalledWith(
      expect.objectContaining({ targetEntityId: target.id, diseaseEntityId: "disease-1", offset: 0 }),
      { limit: 20, stageScope: "overall", targetAggregation: "all" },
      expect.any(AbortSignal),
      "drug",
    ),
  );
  expect(await screen.findByRole("button", { name: "重置筛选" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "重置筛选" }));
  await waitFor(() =>
    expect(searchPipelines).toHaveBeenLastCalledWith(
      expect.objectContaining({ targetEntityId: target.id, diseaseEntityId: "", offset: 0 }),
      { limit: 20, stageScope: "overall", targetAggregation: "all" },
      expect.any(AbortSignal),
      "drug",
    ),
  );
  expect(await screen.findByRole("button", { name: "重置筛选" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "项目明细" }));
  expect(searchPipelines).toHaveBeenCalledWith(
    expect.objectContaining({ targetEntityId: target.id, offset: 0 }),
    { limit: 20, stageScope: "overall", targetAggregation: "all" },
    expect.any(AbortSignal),
    "program",
  );

  fireEvent.change(await screen.findByLabelText("排序方式"), { target: { value: "phase:desc" } });
  await waitFor(() =>
    expect(searchPipelines).toHaveBeenLastCalledWith(
      expect.objectContaining({
        targetEntityId: target.id,
        sortBy: "phase",
        sortDirection: "desc",
        sort: [{ field: "phase", direction: "desc" }],
        offset: 0,
      }),
      { limit: 20, stageScope: "overall", targetAggregation: "all" },
      expect.any(AbortSignal),
      "program",
    ),
  );

  fireEvent.change(await screen.findByRole("combobox", { name: "项目状态" }), { target: { value: "active" } });
  await waitFor(() =>
    expect(searchPipelines).toHaveBeenLastCalledWith(
      expect.objectContaining({ targetEntityId: target.id, programStatus: "active", offset: 0 }),
      { limit: 20, stageScope: "overall", targetAggregation: "all" },
      expect.any(AbortSignal),
      "program",
    ),
  );
  fireEvent.click(await screen.findByRole("button", { name: "下一页" }));
  await waitFor(() =>
    expect(searchPipelines).toHaveBeenLastCalledWith(
      expect.objectContaining({ targetEntityId: target.id, programStatus: "active", offset: 20 }),
      { limit: 20, stageScope: "overall", targetAggregation: "all" },
      expect.any(AbortSignal),
      "program",
    ),
  );
});

it("keeps selected competitor drugs while the user refines and resets the pipeline view", async () => {
  renderTargetView({ initialSection: "pipeline" });

  let competitor = await screen.findByRole("checkbox", { name: "选择对比 Compound A" });
  fireEvent.click(competitor);
  const selectionToolbar = screen.getByRole("toolbar", { name: "竞品候选选择" });
  expect(selectionToolbar).toHaveTextContent("已选 1 个药物");

  fireEvent.change(screen.getByRole("searchbox", { name: "药物或机构" }), {
    target: { value: "dacomitinib" },
  });
  competitor = await screen.findByRole("checkbox", { name: "选择对比 Compound A" });
  expect(competitor).toBeChecked();
  expect(selectionToolbar).toHaveTextContent("已选 1 个药物");

  fireEvent.change(screen.getByRole("combobox", { name: "排序方式" }), {
    target: { value: "phase:desc" },
  });
  competitor = await screen.findByRole("checkbox", { name: "选择对比 Compound A" });
  expect(competitor).toBeChecked();

  fireEvent.click(screen.getByRole("button", { name: "重置筛选" }));
  competitor = await screen.findByRole("checkbox", { name: "选择对比 Compound A" });
  expect(competitor).toBeChecked();
  expect(screen.getByRole("button", { name: "加入列表（1）" })).toBeEnabled();

  fireEvent.click(screen.getByRole("button", { name: "清空选择" }));
  expect(competitor).not.toBeChecked();
  expect(screen.getByRole("button", { name: "加入列表" })).toBeDisabled();
});

it("explains when a target result has no related coverage signals", async () => {
  renderTargetView();

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  const initialSearchResult = vi.mocked(searchPipelines).mock.results[0]?.value;
  if (!initialSearchResult) throw new Error("Missing initial pipeline search result");
  const baselinePipelineResult = (await initialSearchResult) as Awaited<ReturnType<typeof searchPipelines>>;
  vi.mocked(searchPipelines).mockImplementation(async () => ({
    ...baselinePipelineResult,
    facets: {
      ...baselinePipelineResult.facets,
      has_clinical_results: { true: 0, false: baselinePipelineResult.total },
      has_deal: { true: 0, false: baselinePipelineResult.total },
    },
    landscape: {
      ...baselinePipelineResult.landscape,
      distinct_diseases: 0,
      distinct_organizations: 0,
      diseases: [],
      organizations: [],
    },
  }));

  fireEvent.change(await screen.findByRole("combobox", { name: "项目状态" }), {
    target: { value: "inactive" },
  });

  expect(await screen.findByRole("region", { name: "结果覆盖范围" })).toHaveTextContent(
    "关联适应症 0 个 · 研发机构 0 家 · 临床结果 0 条 · 交易披露 0 条",
  );
  expect(
    await screen.findByText(
      "当前结果暂未关联适应症、研发机构、临床结果或交易披露。结果数量反映当前可检索来源中的匹配记录，不代表相关信息不存在。",
    ),
  ).toBeInTheDocument();
});

it("keeps landscape entity filters visible after applying them", async () => {
  renderTargetView();

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  fireEvent.click(await screen.findByRole("button", { name: "可视化" }));

  const combinations = await screen.findByRole("region", { name: "靶点组合" });
  fireEvent.click(within(combinations).getByRole("button", { name: /EGFR \+ MET/ }));
  expect(await screen.findByRole("region", { name: "已应用查询条件" })).toHaveTextContent("靶点组合");
  expect(screen.getByRole("region", { name: "已应用查询条件" })).toHaveTextContent("EGFR + MET");
  await waitFor(() =>
    expect(searchPipelines).toHaveBeenCalledWith(
      expect.objectContaining({ targetCombinationKey: "target-1|target-2" }),
      expect.anything(),
      expect.anything(),
      expect.anything(),
    ),
  );
});

it("commits a landscape filter and the resulting list view as one parent update", async () => {
  const onPipelineSearchChange = vi.fn();
  const onPipelineDisplayModeChange = vi.fn();
  const onPipelineLandscapeFilterApply = vi.fn();
  renderTargetView({
    onPipelineSearchChange,
    onPipelineDisplayModeChange,
    onPipelineLandscapeFilterApply,
  });

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  fireEvent.click(await screen.findByRole("button", { name: "可视化" }));
  onPipelineSearchChange.mockClear();
  onPipelineDisplayModeChange.mockClear();

  const combinations = await screen.findByRole("region", { name: "靶点组合" });
  fireEvent.click(within(combinations).getByRole("button", { name: /EGFR \+ MET/ }));

  expect(onPipelineLandscapeFilterApply).toHaveBeenCalledTimes(1);
  expect(onPipelineLandscapeFilterApply).toHaveBeenCalledWith(
    expect.objectContaining({ targetCombinationKey: "target-1|target-2", offset: 0 }),
    "drug",
  );
  expect(onPipelineSearchChange).not.toHaveBeenCalled();
  expect(onPipelineDisplayModeChange).not.toHaveBeenCalled();
});

it("publishes target pipeline filters so the parent can persist a deep link", async () => {
  const onPipelineSearchChange = vi.fn();
  renderTargetView({ onPipelineSearchChange });

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  fireEvent.change(await screen.findByRole("combobox", { name: "项目状态" }), { target: { value: "active" } });

  await waitFor(() =>
    expect(onPipelineSearchChange).toHaveBeenCalledWith(
      expect.objectContaining({ targetEntityId: target.id, programStatus: "active", offset: 0 }),
    ),
  );
});

it("explains applied target pipeline filters and clears them as one action", async () => {
  const onPipelineSearchChange = vi.fn();
  renderTargetView({
    onPipelineSearchChange,
    initialPipelineFilters: {
      ...emptyPipelineSearchFilters(),
      targetEntityId: target.id,
      query: "EGFR",
      modalities: ["small molecule"],
      phase: "phase_2",
    },
  });

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  const applied = await screen.findByRole("region", { name: "已应用查询条件" });
  expect(applied).toHaveTextContent("药物或机构");
  expect(applied).toHaveTextContent("EGFR");
  expect(applied).toHaveTextContent("小分子");
  expect(applied).toHaveTextContent("II 期");

  fireEvent.click(screen.getByRole("button", { name: "清除全部已应用条件" }));
  await waitFor(() =>
    expect(onPipelineSearchChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        targetEntityId: target.id,
        query: "",
        modalities: [],
        phase: "",
        offset: 0,
      }),
    ),
  );
  expect(screen.queryByRole("region", { name: "已应用查询条件" })).not.toBeInTheDocument();
});

it("explains when a target has no publicly displayable pipeline records", async () => {
  vi.mocked(searchPipelines).mockResolvedValueOnce({
    items: [],
    total: 0,
    project_total: 0,
    result_grain: "drug",
    limit: 100,
    offset: 0,
    sort_by: "status_date",
    sort_direction: "desc",
    sort: [{ field: "status_date", direction: "desc" }],
    query_schema_version: "pharma.pipeline.search.v13",
    applied_filters: [{ field: "target_entity_id", operator: "eq", value: target.id }],
    facets: {},
    landscape: {
      total_programs: 0,
      distinct_drugs: 0,
      distinct_targets: 1,
      distinct_diseases: 0,
      distinct_organizations: 0,
      limit: 20,
      stage_scope: "overall",
      target_aggregation: "all",
      diseases: [],
    },
    as_of: "2026-07-18T11:00:00Z",
    warnings: [],
  } as Awaited<ReturnType<typeof searchPipelines>>);

  renderTargetView();
  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));

  expect(
    await screen.findByText("当前暂无可公开展示的研发项目记录；来源资料正在完成质量核查或尚未覆盖该靶点。"),
  ).toBeInTheDocument();
});

it("disables empty pipeline facet choices without disabling a selected zero-count deep link", async () => {
  vi.mocked(searchPipelines).mockResolvedValueOnce({
    items: [],
    total: 0,
    project_total: 0,
    result_grain: "drug",
    limit: 100,
    offset: 0,
    sort_by: "status_date",
    sort_direction: "desc",
    sort: [{ field: "status_date", direction: "desc" }],
    query_schema_version: "pharma.pipeline.search.v13",
    applied_filters: [{ field: "target_entity_id", operator: "eq", value: target.id }],
    facets: {
      program_status: { active: 0, inactive: 0, unknown: 0 },
      has_clinical_results: { true: 0, false: 0 },
      has_deal: { true: 0, false: 0 },
    },
    landscape: {
      total_programs: 0,
      distinct_drugs: 0,
      distinct_targets: 1,
      distinct_diseases: 0,
      distinct_organizations: 0,
      limit: 20,
      stage_scope: "overall",
      target_aggregation: "all",
      diseases: [],
    },
    as_of: "2026-07-18T11:00:00Z",
    warnings: [],
  } as Awaited<ReturnType<typeof searchPipelines>>);

  renderTargetView({
    initialPipelineFilters: {
      ...emptyPipelineSearchFilters(),
      targetEntityId: target.id,
      programStatus: "active",
    },
  });

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  expect(await screen.findByRole("option", { name: "在研 (0)" })).toBeEnabled();
  expect(screen.getByRole("option", { name: "已停止 (0)" })).toBeDisabled();
  expect(screen.getByRole("option", { name: "状态未披露 (0)" })).toBeDisabled();
  expect(screen.getByRole("option", { name: "已有结果 (0)" })).toBeDisabled();
  expect(screen.getByRole("option", { name: "暂无结果 (0)" })).toBeDisabled();
  expect(screen.getByRole("option", { name: "已有交易 (0)" })).toBeDisabled();
  expect(screen.getByRole("option", { name: "暂无交易 (0)" })).toBeDisabled();
});

it("debounces free-text pipeline queries while typing", async () => {
  renderTargetView();

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  const queryInput = await screen.findByRole("searchbox", { name: "药物或机构" });
  const callsBeforeTyping = vi.mocked(searchPipelines).mock.calls.length;

  fireEvent.change(queryInput, { target: { value: "E" } });
  fireEvent.change(queryInput, { target: { value: "EG" } });
  fireEvent.change(queryInput, { target: { value: "EGFR" } });

  expect(vi.mocked(searchPipelines).mock.calls).toHaveLength(callsBeforeTyping);
  await waitFor(() =>
    expect(vi.mocked(searchPipelines).mock.calls.at(-1)?.[0]).toEqual(
      expect.objectContaining({ query: "EGFR", targetEntityId: target.id, offset: 0 }),
    ),
  );
  expect(vi.mocked(searchPipelines).mock.calls).toHaveLength(callsBeforeTyping + 1);
});

it("labels a drug with multiple project states as mixed instead of only active", () => {
  expect(
    pipelineProgramStatusLabel({ program_status: "active", program_status_counts: { active: 2, inactive: 1 } }),
  ).toBe("混合状态");
  expect(pipelineProgramStatusLabel({ program_status: "active", program_status_counts: { active: 2 } })).toBe("在研");
});

it("keeps a selected single-value facet visible when the next result has no matches", () => {
  expect(pipelineSelectOptions("phase_3", { phase_2: 3 })).toEqual([
    ["phase_2", 3],
    ["phase_3", 0],
  ]);
});

it("publishes clinical and deal signal filters and clears dependent values", async () => {
  const onPipelineSearchChange = vi.fn();
  renderTargetView({
    onPipelineSearchChange,
    initialPipelineFilters: {
      ...emptyPipelineSearchFilters(),
      targetEntityId: target.id,
      clinicalResultEvaluation: "positive",
      dealCurrency: "USD",
      dealTotalPotentialAmountMin: "100",
      dealTotalPotentialAmountMax: "200",
    },
  });

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  fireEvent.change(await screen.findByRole("combobox", { name: "临床结果" }), { target: { value: "false" } });

  await waitFor(() =>
    expect(onPipelineSearchChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        targetEntityId: target.id,
        hasClinicalResults: "false",
        clinicalResultEvaluation: "",
        offset: 0,
      }),
    ),
  );

  fireEvent.change(await screen.findByRole("combobox", { name: "交易信号" }), { target: { value: "false" } });

  await waitFor(() =>
    expect(onPipelineSearchChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        targetEntityId: target.id,
        hasDeal: "false",
        dealCurrency: "",
        dealTotalPotentialAmountMin: "",
        dealTotalPotentialAmountMax: "",
        offset: 0,
      }),
    ),
  );
});

it("describes the active pipeline filter while the result is loading", async () => {
  vi.mocked(searchPipelines).mockImplementationOnce(() => new Promise(() => {}));
  renderTargetView({
    initialPipelineFilters: {
      ...emptyPipelineSearchFilters(),
      targetEntityId: target.id,
      programStatus: "active",
    },
  });

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));

  expect(await screen.findByText("正在加载 EGFR 的在研项目")).toBeInTheDocument();
});

it("publishes target pipeline display and analysis state for a deep link", async () => {
  const onPipelineDisplayModeChange = vi.fn();
  const onPipelineAnalysisChange = vi.fn();
  renderTargetView({ onPipelineDisplayModeChange, onPipelineAnalysisChange });

  fireEvent.click(await screen.findByRole("tab", { name: "竞品管线" }));
  fireEvent.click(await screen.findByRole("button", { name: "可视化" }));

  expect(onPipelineDisplayModeChange).toHaveBeenCalledWith("landscape");
  fireEvent.change(await screen.findByRole("combobox", { name: "分析维度" }), {
    target: { value: "targets" },
  });
  await waitFor(() =>
    expect(onPipelineAnalysisChange).toHaveBeenCalledWith(
      expect.objectContaining({ dimension: "targets", view: "chart", limit: 20 }),
    ),
  );
});

it("loads assay-compatible SAR comparison with ranks, filters, entity links and provenance", async () => {
  const onOpenEntity = vi.fn();
  renderTargetView({ onOpenEntity });

  fireEvent.click(await screen.findByRole("tab", { name: "SAR 对比" }));
  expect(await screen.findByText("VX-101")).toBeInTheDocument();
  expect(screen.getByText("可组内比较")).toBeInTheDocument();
  expect(screen.getByText("不可直接比较")).toBeInTheDocument();
  expect(screen.getByText("上下限或近似值；缺少 Assay 类型；缺少 Assay 格式")).toBeInTheDocument();
  expect(loadTargetSar).toHaveBeenCalledWith(
    target.id,
    {
      standardType: "",
      assayType: "",
      assayFormat: "",
      organism: "",
      cellLine: "",
      offset: 0,
    },
    expect.any(AbortSignal),
  );
  fireEvent.click(screen.getByRole("button", { name: "VX-101" }));
  expect(onOpenEntity).toHaveBeenCalledWith("compound-1");
  fireEvent.click(screen.getByRole("button", { name: "查看 VX-101 SAR 的原始证据" }));
  await waitFor(() =>
    expect(loadRecordProvenance).toHaveBeenCalledWith(
      {
        resourceType: "activity_measurement",
        resourceId: "77777777-7777-4777-8777-777777777777",
        label: "VX-101 SAR",
      },
      expect.any(AbortSignal),
    ),
  );
  fireEvent.change(screen.getByLabelText("Assay 类型"), { target: { value: "binding" } });
  await waitFor(() => expect(loadTargetSar).toHaveBeenCalledTimes(2));
});

it("opens stable professional deal and regulatory details from the target dossier", async () => {
  const base = await vi.mocked(loadTargetDossier)("template", new AbortController().signal);
  vi.mocked(loadTargetDossier).mockResolvedValue({
    ...base,
    deals: [
      {
        id: "deal-1",
        entity_id: "transaction-1",
        name: "Acme Pharma license",
        deal_type: "license",
        status: "active",
        direction: "outbound",
        direction_reference_jurisdiction: "US",
        announced_at: "2026-06-01T00:00:00Z",
        terminated_at: null,
        source_updated_at: "2026-06-02T00:00:00Z",
        parties: [{ entity_id: "org-1", name: "Acme Pharma" }],
        asset_entity_ids: ["drug-1"],
        territory: "Global",
        upfront_amount: 25_000_000,
        total_potential_amount: 500_000_000,
        currency: "USD",
        terms: {},
        source_document_id: "document-2",
        party_entities: [{ id: "org-1", name: "Acme Pharma", entity_type: "organization" }],
        asset_entities: [{ id: "drug-1", name: "Compound A", entity_type: "drug" }],
        party_roles: [],
        asset_stages: [],
        rights: [],
      },
    ],
    regulatory_events: [
      {
        id: "regulatory-1",
        subject_entity_id: "drug-1",
        agency: "FDA",
        jurisdiction: "US",
        event_identifier: "FDA-2026-001",
        application_number: "NDA 219999",
        event_type: "approval",
        status: "approved",
        title: "Compound A approved",
        decision_date: "2026-07-01T00:00:00Z",
        indication_entity_id: null,
        organization_entity_id: "org-1",
        details: {},
        designation_type: null,
        label_change_type: null,
        label_version: null,
        label_effective_at: null,
        approved_population: null,
        line_of_therapy: null,
        biomarker: null,
        route_of_administration: null,
        dosage_form: null,
        has_boxed_warning: null,
        safety_signal_type: null,
        safety_term: null,
        safety_severity: null,
        safety_status: null,
        safety_identified_at: null,
        safety_confirmed_at: null,
        safety_resolved_at: null,
        affected_population: null,
        risk_actions: [],
        source_updated_at: "2026-07-02T00:00:00Z",
        source_document_id: "document-3",
        subject_entity: { id: "drug-1", name: "Compound A", entity_type: "drug" },
        indication_entity: null,
        organization_entity: { id: "org-1", name: "Acme Pharma", entity_type: "organization" },
      },
    ],
  });
  const onOpenDeal = vi.fn();
  const onOpenRegulatoryEvent = vi.fn();
  renderTargetView({ onOpenDeal, onOpenRegulatoryEvent });

  fireEvent.click(await screen.findByRole("tab", { name: "交易" }));
  fireEvent.click(screen.getByRole("button", { name: "打开交易详情：Acme Pharma" }));
  expect(onOpenDeal).toHaveBeenCalledWith("deal-1");

  fireEvent.click(screen.getByRole("tab", { name: "监管动态" }));
  fireEvent.click(screen.getByRole("button", { name: "打开监管事件详情：Compound A approved" }));
  expect(onOpenRegulatoryEvent).toHaveBeenCalledWith("regulatory-1");
});

it("opens stable professional patent and news details from the target dossier", async () => {
  const base = await vi.mocked(loadTargetDossier)("template", new AbortController().signal);
  vi.mocked(loadTargetDossier).mockResolvedValue({
    ...base,
    patents: [
      {
        id: "patent-1",
        entity_id: "patent-entity-1",
        family_identifier: "WO2026000001",
        title: "EGFR inhibitor patent",
        priority_date: "2024-01-10T00:00:00Z",
        applicants: ["Acme Pharma"],
        inventors: [],
        publications: [],
        legal_status: "ACTIVE",
        legal_status_at: "2026-01-01T00:00:00Z",
        legal_events: [],
        independent_claims: [],
        expiration_date: "2044-01-10T00:00:00Z",
        linked_entity_ids: [target.id],
        source_document_id: "document-4",
      },
    ],
    news_events: [
      {
        id: "news-1",
        event_identifier: "NEWS-2026-1",
        event_type: "publication",
        title: "EGFR translational update",
        summary: "Governed translational update",
        published_at: "2026-07-03T00:00:00Z",
        language: "en",
        publisher_entity_id: "org-1",
        related_entity_ids: [target.id],
        canonical_url: "https://example.test/news-1",
        venue: null,
        details: {},
        source_document_id: "document-5",
        publisher_entity: null,
        related_entities: [],
      },
    ],
  });
  const onOpenPatent = vi.fn();
  const onOpenNewsEvent = vi.fn();
  renderTargetView({ onOpenPatent, onOpenNewsEvent });

  fireEvent.click(await screen.findByRole("tab", { name: "专利" }));
  fireEvent.click(screen.getByRole("button", { name: "打开专利族详情：WO2026000001" }));
  expect(onOpenPatent).toHaveBeenCalledWith("patent-1");

  fireEvent.click(screen.getByRole("tab", { name: "新闻与会议" }));
  fireEvent.click(screen.getByRole("button", { name: "打开新闻事件详情：EGFR translational update" }));
  expect(onOpenNewsEvent).toHaveBeenCalledWith("news-1");
});
