import { fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { type CompanyDossier, loadCompanyDossier } from "../lib/contracts/company";
import type { Entity } from "../lib/types";
import type { CompanyDossierSection } from "../lib/workspaceRouting";
import { CompanyView } from "../views/CompanyView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/company", () => ({
  companyKeys: { dossier: (companyId: string) => ["company-dossier", companyId] },
  loadCompanyDossier: vi.fn(),
}));

const company: Entity = {
  id: "company-1",
  canonical_entity_id: "company-1",
  entity_type: "organization",
  name: "Vector Pharma",
  description: "经治理的创新药研发公司",
  external_ids: { lei: "VECTOR-LEI" },
  attributes: { headquarters: "Shanghai" },
  review_status: "verified",
  created_at: "2026-07-20T08:00:00Z",
  updated_at: "2026-07-25T08:00:00Z",
};

const program: CompanyDossier["programs"][number] = {
  id: "program-1",
  drug_entity_id: "drug-1",
  drug_name: "VX-101",
  target_entity_id: "target-1",
  target_name: "EGFR",
  disease_entity_id: "disease-1",
  disease_name: "非小细胞肺癌",
  organization_entity_id: company.id,
  organization_name: company.name,
  modality: "small molecule",
  mechanism_of_action: "EGFR inhibitor",
  phase: "phase_2",
  global_phase: "phase_2",
  china_phase: "phase_1",
  status_detail: "active",
  status_date: "2026-07-24T00:00:00Z",
  geography: "global",
  source_document_id: "document-1",
  milestones: [],
};

const dossier: CompanyDossier = {
  entity: {
    ...company,
    canonical_entity_id: company.id,
    identity_identifiers: [],
    review_status: "verified",
  },
  summary: {
    program_count: 2,
    drug_count: 1,
    target_count: 1,
    indication_count: 1,
    deal_count: 1,
    timeline_event_count: 2,
    modalities: ["small molecule"],
    phase_distribution: { phase_2: 1, preclinical: 1 },
    highest_phase: "phase_2",
    latest_activity_at: "2026-07-24T00:00:00Z",
  },
  timeline: {
    company: {
      ...company,
      canonical_entity_id: company.id,
      identity_identifiers: [],
      review_status: "verified",
    },
    items: [
      {
        id: "program_status:program-1",
        event_type: "program_status",
        occurred_at: "2026-07-24T00:00:00Z",
        title: "VX-101 · phase_2",
        program,
        deal: null,
      },
    ],
    total: 2,
    limit: 100,
    offset: 0,
    facets: { event_type: { program_status: 2 }, phase: { phase_2: 1, preclinical: 1 }, deal_type: {} },
    as_of: "2026-07-25T12:00:00Z",
    warnings: ["时间线只包含具有明确日期的记录。"],
  },
  relationships: [],
  activities: [],
  programs: [program],
  clinical_trials: [],
  patents: [],
  deals: [],
  regulatory_events: [],
  news_events: [],
  structures: [],
  target_evidence: [],
  coverage: [
    { domain: "programs", total: 2, returned: 1, status: "truncated", note: "本次返回 1 条" },
    { domain: "deals", total: 1, returned: 0, status: "truncated", note: "交易由专业分区读取" },
    { domain: "clinical_trials", total: 0, returned: 0, status: "not_observed", note: "当前未观察到" },
  ],
  as_of: "2026-07-25T12:00:00Z",
  warnings: ["未观察到记录不代表公司不存在相关活动。"],
};

function renderCompanyView(
  entity: Entity | null = company,
  {
    initialSection = "overview",
    onOpenEntity = vi.fn(),
    onOpenDrug,
    onOpenTarget,
    onOpenDisease,
    onOpenOrganization,
  }: {
    initialSection?: CompanyDossierSection;
    onOpenEntity?: (entityId: string) => void;
    onOpenDrug?: (drugId: string) => void;
    onOpenTarget?: (targetId: string) => void;
    onOpenDisease?: (diseaseId: string) => void;
    onOpenOrganization?: (organizationId: string) => void;
  } = {},
) {
  function Harness() {
    const [activeSection, setActiveSection] = useState<CompanyDossierSection>(initialSection);
    return (
      <CompanyView
        company={entity}
        activeSection={activeSection}
        onSectionChange={setActiveSection}
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

  return renderWithQueryClient(<Harness />);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(loadCompanyDossier).mockResolvedValue(dossier);
});

it("renders the governed company summary, portfolio and stable professional sections", async () => {
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenTarget = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  renderCompanyView(company, { onOpenEntity, onOpenDrug, onOpenTarget, onOpenDisease, onOpenOrganization });

  expect(await screen.findByRole("heading", { name: "Vector Pharma" })).toBeInTheDocument();
  expect(loadCompanyDossier).toHaveBeenCalledWith("company-1", expect.any(AbortSignal));
  expect(screen.queryAllByText(/已确认|已查证/)).toHaveLength(0);
  expect(screen.getAllByText("II 期临床")).toHaveLength(2);
  expect(screen.getByRole("list", { name: "公司研发阶段分布" })).toContainElement(screen.getByText("临床前"));
  expect(screen.getByText("VX-101 · phase_2")).toBeInTheDocument();
  expect(screen.getByText("未观察到记录不代表公司不存在相关活动。")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "VX-101" }));
  expect(onOpenDrug).toHaveBeenCalledWith("drug-1");
  expect(onOpenEntity).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("tab", { name: "研发管线" }));
  expect(screen.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("EGFR inhibitor")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Vector Pharma" }));
  fireEvent.click(screen.getByRole("button", { name: "非小细胞肺癌" }));
  fireEvent.click(screen.getByRole("button", { name: "EGFR" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("company-1");
  expect(onOpenDisease).toHaveBeenCalledWith("disease-1");
  expect(onOpenTarget).toHaveBeenCalledWith("target-1");

  fireEvent.click(screen.getByRole("tab", { name: "公司时间线" }));
  expect(screen.getByText("管线状态与交易公告")).toBeInTheDocument();
  expect(screen.getByText("时间线只包含具有明确日期的记录。")).toBeInTheDocument();
});

it("uses public product copy when a company summary is unavailable", async () => {
  vi.mocked(loadCompanyDossier).mockResolvedValueOnce({
    ...dossier,
    entity: { ...dossier.entity, description: null },
  });
  renderCompanyView();

  expect(await screen.findByText("暂无公司简介")).toBeInTheDocument();
  expect(screen.queryByText("暂无经治理的公司摘要")).not.toBeInTheDocument();
});

it("prioritizes registered trials and an identity caveat for provider-scoped sponsor names", async () => {
  const note = "ClinicalTrials.gov申办方名称，不代表已核实的法律主体或企业集团归并。";
  vi.mocked(loadCompanyDossier).mockResolvedValueOnce({
    ...dossier,
    entity: {
      ...dossier.entity,
      description: null,
      attributes: { identity_scope: "provider_label", label_provider: "ClinicalTrials.gov", identity_note: note },
    },
    programs: [],
    summary: { ...dossier.summary, program_count: 0, drug_count: 0, phase_distribution: {}, highest_phase: null },
  });
  renderCompanyView();

  expect(await screen.findByText(note)).toBeInTheDocument();
  expect(screen.getByText("登记申办方名称")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "登记临床试验" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "登记临床试验（0）" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "全部登记试验" })).toBeDisabled();
  expect(screen.queryByText("暂无可统计研发阶段")).not.toBeInTheDocument();
  expect(screen.queryByText("研发项目 / 药物")).not.toBeInTheDocument();
});

it("renders a recoverable company dossier error", async () => {
  vi.mocked(loadCompanyDossier).mockRejectedValueOnce(new Error("Company service unavailable"));
  renderCompanyView();

  expect(await screen.findByText("Company service unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
});

it("fails closed for a non-company deep link without calling the company endpoint", () => {
  renderCompanyView({ ...company, entity_type: "drug", name: "VX-101" });

  expect(screen.getByText("该深链接不是机构实体，无法打开公司专业档案")).toBeInTheDocument();
  expect(loadCompanyDossier).not.toHaveBeenCalled();
});
