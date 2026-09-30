import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { loadCompanyTimeline } from "../lib/contracts/company";
import { loadEntityDossier } from "../lib/contracts/entityDossier";
import { loadRecordProvenance } from "../lib/contracts/provenance";
import type { Entity } from "../lib/types";
import type { EntityDossierSection } from "../lib/workspaceRouting";
import { EntityDossierView } from "../views/EntityDossierView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/entityDossier", () => ({
  entityDossierKeys: { detail: (entityId: string) => ["entity-dossier", entityId] },
  loadEntityDossier: vi.fn(),
}));

vi.mock("../lib/contracts/company", () => ({
  companyKeys: { timeline: (companyId: string, offset: number) => ["company-timeline", companyId, offset] },
  loadCompanyTimeline: vi.fn(),
}));

vi.mock("../lib/contracts/provenance", () => ({
  provenanceKeys: {
    record: (resourceType: string, resourceId: string) => ["provenance", resourceType, resourceId],
  },
  loadRecordProvenance: vi.fn(),
}));

const drug: Entity = {
  id: "drug-1",
  canonical_entity_id: "drug-1",
  entity_type: "drug",
  name: "Compound A",
  description: "Governed small-molecule candidate",
  external_ids: { chembl: "CHEMBL1" },
  attributes: { modality: "small molecule" },
  review_status: "verified",
  created_at: "2026-07-21T10:00:00Z",
  updated_at: "2026-07-22T10:00:00Z",
};

function renderEntityDossier(
  entity: Entity,
  {
    initialSection = "overview",
    onOpenEntity = vi.fn(),
    onOpenDrug,
    onOpenTarget,
    onOpenDisease,
    onOpenOrganization,
    onOpenPatent = vi.fn(),
    onOpenDeal = vi.fn(),
    onOpenRegulatoryEvent = vi.fn(),
    onOpenNewsEvent = vi.fn(),
  }: {
    initialSection?: EntityDossierSection;
    onOpenEntity?: (entityId: string) => void;
    onOpenDrug?: (drugId: string) => void;
    onOpenTarget?: (targetId: string) => void;
    onOpenDisease?: (diseaseId: string) => void;
    onOpenOrganization?: (organizationId: string) => void;
    onOpenPatent?: (patentId: string) => void;
    onOpenDeal?: (dealId: string) => void;
    onOpenRegulatoryEvent?: (eventId: string) => void;
    onOpenNewsEvent?: (eventId: string) => void;
  } = {},
) {
  function Harness() {
    const [activeSection, setActiveSection] = useState<EntityDossierSection>(initialSection);
    return (
      <EntityDossierView
        entity={entity}
        activeSection={activeSection}
        onSectionChange={(section) => setActiveSection(section)}
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
      />
    );
  }

  return renderWithQueryClient(<Harness />);
}

beforeEach(() => {
  vi.mocked(loadEntityDossier).mockResolvedValue({
    entity: {
      ...drug,
      canonical_entity_id: drug.id,
      identity_identifiers: [],
      review_status: "verified" as const,
    },
    relationships: [
      {
        id: "relationship-1",
        predicate: "has_target",
        direction: "outgoing",
        related_entity: {
          ...drug,
          id: "target-1",
          canonical_entity_id: "target-1",
          entity_type: "target",
          name: "EGFR",
          identity_identifiers: [],
          review_status: "verified" as const,
        },
        attributes: {},
        review_status: "verified",
        valid_from: null,
        valid_to: null,
      },
    ],
    activities: [],
    programs: [
      {
        id: "program-1",
        drug_entity_id: drug.id,
        drug_name: drug.name,
        target_entity_id: "target-1",
        target_name: "EGFR",
        disease_entity_id: "disease-1",
        disease_name: "Lung cancer",
        organization_entity_id: "org-1",
        organization_name: "Acme Pharma",
        modality: "small molecule",
        mechanism_of_action: "EGFR inhibitor",
        phase: "phase_2",
        status_detail: "active",
        status_date: "2026-07-01T00:00:00Z",
        geography: "global",
        status_history: [],
        milestones: [],
        source_document_id: "document-1",
      },
    ],
    clinical_trials: [],
    patents: [],
    deals: [],
    regulatory_events: [],
    news_events: [],
    structures: [],
    target_evidence: [],
    coverage: [
      { domain: "relationships", total: 1, returned: 1, status: "available", note: "已返回当前匹配记录" },
      { domain: "evidence", total: 1, returned: 0, status: "available", note: "按许可读取" },
      { domain: "activities", total: 0, returned: 0, status: "not_observed", note: "当前未观察到" },
      { domain: "programs", total: 1, returned: 1, status: "available", note: "已返回当前匹配记录" },
      { domain: "clinical_trials", total: 0, returned: 0, status: "not_observed", note: "当前未观察到" },
      { domain: "patents", total: 0, returned: 0, status: "not_observed", note: "当前未观察到" },
      { domain: "deals", total: 0, returned: 0, status: "not_observed", note: "当前未观察到" },
      { domain: "regulatory_events", total: 0, returned: 0, status: "not_observed", note: "当前未观察到" },
      { domain: "news_events", total: 0, returned: 0, status: "not_observed", note: "当前未观察到" },
      { domain: "structures", total: 0, returned: 0, status: "not_observed", note: "当前未观察到" },
    ],
    as_of: "2026-07-22T12:00:00Z",
    warnings: ["未观察到记录不代表全球不存在。"],
  });
  vi.mocked(loadRecordProvenance).mockResolvedValue({
    resource_type: "development_program",
    resource_id: "program-1",
    items: [],
    license_scopes: [],
    warnings: [],
  });
  vi.mocked(loadCompanyTimeline).mockResolvedValue({
    company: {
      ...drug,
      id: "org-1",
      canonical_entity_id: "org-1",
      entity_type: "organization",
      name: "Acme Pharma",
      identity_identifiers: [],
      review_status: "verified" as const,
    },
    items: [],
    total: 0,
    limit: 100,
    offset: 0,
    facets: {},
    as_of: "2026-07-22T12:00:00Z",
    warnings: [],
  });
});

it("loads a governed multi-domain dossier with explicit coverage and controlled tabs", async () => {
  renderEntityDossier(drug);

  expect(await screen.findByRole("heading", { name: "Compound A" })).toBeInTheDocument();
  expect(loadEntityDossier).toHaveBeenCalledWith("drug-1", expect.any(AbortSignal));
  expect(screen.getByText("未观察到记录不代表全球不存在。")).toBeInTheDocument();
  expect(screen.getByText("CHEMBL1")).toBeInTheDocument();
  expect(screen.queryByText("信息质量")).not.toBeInTheDocument();
  expect(screen.queryAllByText(/已确认|已查证/)).toHaveLength(0);

  fireEvent.click(screen.getByRole("tab", { name: "关系网络" }));
  expect(screen.queryByRole("columnheader", { name: "状态" })).not.toBeInTheDocument();
  expect(screen.getByText("has_target")).toBeInTheDocument();
  expect(screen.getByText("EGFR")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("tab", { name: "研发管线" }));
  expect(screen.getByText("Acme Pharma")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "查看 Compound A 的原始证据" }));
  expect(await screen.findByRole("heading", { name: "原始证据" })).toBeInTheDocument();
  expect(loadRecordProvenance).toHaveBeenCalledWith(
    { resourceType: "development_program", resourceId: "program-1", label: "Compound A" },
    expect.any(AbortSignal),
  );
});

it("renders an explicit empty state instead of implying global absence", async () => {
  renderEntityDossier(drug);
  fireEvent.click(await screen.findByRole("tab", { name: "活性数据" }));
  expect(screen.getByText("暂无关联活性数据")).toBeInTheDocument();
});

it("opens an available domain directly from the dossier coverage summary", async () => {
  renderEntityDossier(drug);
  fireEvent.click(await screen.findByRole("button", { name: "查看研发管线" }));
  expect(screen.getByText("Acme Pharma")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
});

it("fails closed when a non-company deep link requests company intelligence", async () => {
  const onSectionChange = vi.fn();
  renderWithQueryClient(
    <EntityDossierView
      entity={drug}
      activeSection="company_intelligence"
      onSectionChange={onSectionChange}
      onOpenEntity={vi.fn()}
      onOpenTrial={vi.fn()}
      onOpenPatent={vi.fn()}
      onOpenDeal={vi.fn()}
      onOpenRegulatoryEvent={vi.fn()}
      onOpenNewsEvent={vi.fn()}
    />,
  );

  expect(await screen.findByRole("heading", { name: "Compound A" })).toBeInTheDocument();
  await waitFor(() => expect(onSectionChange).toHaveBeenCalledWith("overview", true));
  expect(screen.queryByRole("tab", { name: "公司情报" })).not.toBeInTheDocument();
  expect(screen.getByRole("tabpanel")).toHaveAttribute("id", "entity-dossier-panel-overview");
});

it("shows a company-only intelligence tab with the shared pipeline and transaction timeline", async () => {
  const base = await vi.mocked(loadEntityDossier)("template", new AbortController().signal);
  const company = {
    ...drug,
    id: "org-1",
    canonical_entity_id: "org-1",
    entity_type: "organization" as const,
    name: "Acme Pharma",
    review_status: "verified" as const,
  };
  vi.mocked(loadEntityDossier).mockResolvedValue({
    ...base,
    entity: { ...base.entity, ...company, identity_identifiers: [] },
  });
  vi.mocked(loadCompanyTimeline).mockResolvedValue({
    company: { ...base.entity, ...company, identity_identifiers: [] },
    items: [
      {
        id: "program_status:program-1",
        event_type: "program_status",
        occurred_at: "2026-07-01T00:00:00Z",
        title: "Compound A · phase_2",
        program: base.programs[0],
        deal: null,
      },
      {
        id: "deal_announced:deal-1",
        event_type: "deal_announced",
        occurred_at: "2026-06-01T00:00:00Z",
        title: "Compound A global license",
        program: null,
        deal: {
          id: "deal-1",
          entity_id: "transaction-1",
          name: "Compound A global license",
          deal_type: "license",
          status: "active",
          direction: "global",
          direction_reference_jurisdiction: null,
          announced_at: "2026-06-01T00:00:00Z",
          terminated_at: null,
          source_updated_at: "2026-06-01T00:00:00Z",
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
      },
    ],
    total: 2,
    limit: 100,
    offset: 0,
    facets: {
      event_type: { program_status: 1, deal_announced: 1 },
      phase: { phase_2: 1 },
      deal_type: { license: 1 },
    },
    as_of: "2026-07-22T12:00:00Z",
    warnings: ["时间线仅包含具有明确日期的事件。"],
  });

  renderEntityDossier(company);

  fireEvent.click(await screen.findByRole("tab", { name: "公司情报" }));
  expect(await screen.findByRole("heading", { name: "公司研发管线" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "管线状态与交易公告" })).toBeInTheDocument();
  expect(screen.getByText("Compound A global license")).toBeInTheDocument();
  expect(screen.getByText("时间线仅包含具有明确日期的事件。")).toBeInTheDocument();
  expect(loadCompanyTimeline).toHaveBeenCalledWith("org-1", 0, expect.any(AbortSignal));
});

it("opens stable professional deal and regulatory details from the source dossier", async () => {
  const base = await vi.mocked(loadEntityDossier)("template", new AbortController().signal);
  vi.mocked(loadEntityDossier).mockResolvedValue({
    ...base,
    deals: [
      {
        id: "deal-1",
        entity_id: "transaction-1",
        name: "Compound A global license",
        deal_type: "license",
        status: "active",
        direction: "outbound",
        direction_reference_jurisdiction: "US",
        announced_at: "2026-06-01T00:00:00Z",
        terminated_at: null,
        source_updated_at: "2026-06-02T00:00:00Z",
        parties: [],
        asset_entity_ids: ["drug-1"],
        territory: "Global",
        upfront_amount: 25_000_000,
        total_potential_amount: 500_000_000,
        currency: "USD",
        terms: {},
        source_document_id: "document-2",
        party_entities: [{ id: "org-1", name: "Acme Pharma", entity_type: "organization" }],
        asset_entities: [{ id: "drug-1", name: "Compound A", entity_type: "drug" }],
        party_roles: [
          {
            id: "org-1",
            name: "Acme Pharma",
            entity_type: "organization",
            role: "licensor",
            country_region: "US",
            organization_type: "biopharma",
          },
        ],
        asset_stages: [
          {
            id: "drug-1",
            name: "Compound A",
            entity_type: "drug",
            development_phase_at_transaction: "phase_2",
            current_development_phase: "phase_2",
            current_phase_as_of: "2026-07-01T00:00:00Z",
          },
        ],
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
  const onOpenEntity = vi.fn();
  const onOpenOrganization = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenRegulatoryEvent = vi.fn();
  renderEntityDossier(drug, {
    onOpenDeal,
    onOpenEntity,
    onOpenOrganization,
    onOpenDrug,
    onOpenRegulatoryEvent,
  });

  fireEvent.click(await screen.findByRole("tab", { name: "交易" }));
  expect(screen.getByRole("button", { name: "Acme Pharma · 许可方" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Compound A · II期" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "打开交易详情：Compound A global license" }));
  expect(onOpenDeal).toHaveBeenCalledWith("deal-1");
  fireEvent.click(screen.getByRole("button", { name: "Acme Pharma · 许可方" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("org-1");
  fireEvent.click(screen.getByRole("button", { name: "Compound A · II期" }));
  expect(onOpenDrug).toHaveBeenCalledWith("drug-1");
  expect(onOpenEntity).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("tab", { name: "监管" }));
  fireEvent.click(screen.getByRole("button", { name: "打开监管事件详情：Compound A approved" }));
  expect(onOpenRegulatoryEvent).toHaveBeenCalledWith("regulatory-1");
});

it("opens stable professional patent and news details from the source dossier", async () => {
  const base = await vi.mocked(loadEntityDossier)("template", new AbortController().signal);
  vi.mocked(loadEntityDossier).mockResolvedValue({
    ...base,
    patents: [
      {
        id: "patent-1",
        entity_id: "patent-entity-1",
        family_identifier: "WO2026000001",
        title: "Compound A composition patent",
        priority_date: "2024-01-10T00:00:00Z",
        applicants: ["Acme Pharma"],
        inventors: [],
        publications: [],
        legal_status: "ACTIVE",
        legal_status_at: "2026-01-01T00:00:00Z",
        legal_events: [],
        independent_claims: [],
        expiration_date: "2044-01-10T00:00:00Z",
        linked_entity_ids: ["drug-1"],
        source_document_id: "document-4",
      },
    ],
    news_events: [
      {
        id: "news-1",
        event_identifier: "NEWS-2026-1",
        event_type: "press_release",
        title: "Compound A development update",
        summary: "Governed development update",
        published_at: "2026-07-03T00:00:00Z",
        language: "en",
        publisher_entity_id: "org-1",
        related_entity_ids: ["drug-1"],
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
  renderEntityDossier(drug, { onOpenPatent, onOpenNewsEvent });

  fireEvent.click(await screen.findByRole("tab", { name: "专利" }));
  fireEvent.click(screen.getByRole("button", { name: "打开专利族详情：WO2026000001" }));
  expect(onOpenPatent).toHaveBeenCalledWith("patent-1");

  fireEvent.click(screen.getByRole("tab", { name: "动态" }));
  fireEvent.click(screen.getByRole("button", { name: "打开新闻事件详情：Compound A development update" }));
  expect(onOpenNewsEvent).toHaveBeenCalledWith("news-1");
});
