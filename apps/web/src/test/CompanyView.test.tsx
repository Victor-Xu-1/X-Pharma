import { fireEvent, screen, within } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { loadCompanyDossier } from "../lib/contracts/company";
import type { Entity } from "../lib/types";
import type { CompanyDossierSection } from "../lib/workspaceRouting";
import { CompanyView } from "../views/CompanyView";
import { company, dossier } from "./fixtures/companyDossier";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/company", () => ({
  companyKeys: { dossier: (companyId: string) => ["company-dossier", companyId] },
  loadCompanyDossier: vi.fn(),
}));

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
  expect(within(screen.getByRole("list", { name: "已返回研发资产" })).getByText("II 期临床")).toBeInTheDocument();
  expect(document.querySelector(".company-profile-metrics")).toHaveTextContent("II 期临床");
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
