import { fireEvent, screen, within } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { type DrugProgramPage, loadDrugDossier, loadDrugPrograms } from "../lib/contracts/drugDossier";
import type { Entity } from "../lib/types";
import type { DrugDossierSection } from "../lib/workspaceRouting";
import { DrugView } from "../views/DrugView";
import { drugDossierFixture as dossier, drug } from "./fixtures/drugDossier";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/drugDossier", () => ({
  drugDossierKeys: { detail: (drugId: string) => ["drug-dossier", drugId] },
  drugProgramKeys: { page: (drugId: string, offset: number) => ["drug-programs", drugId, offset] },
  loadDrugDossier: vi.fn(),
  loadDrugPrograms: vi.fn(),
}));

vi.mock("../components/MoleculeDepiction", () => ({
  MoleculeDepiction: ({ name, smiles }: { name: string; smiles: string }) => (
    <div role="img" aria-label={`${name} 结构图`} data-smiles={smiles} />
  ),
}));

function makeProgramPage(offset = 0, items = dossier.programs, total = dossier.summary.program_count): DrugProgramPage {
  return {
    query_schema_version: "pharma.drug.programs.v1",
    items,
    total,
    limit: 100,
    offset,
    as_of: dossier.as_of,
    warnings: dossier.warnings,
  };
}

function renderDrugView(
  entity: Entity | null = drug,
  {
    initialSection = "overview",
    onOpenEntity = vi.fn(),
    onOpenDrug = vi.fn(),
    onOpenTarget = vi.fn(),
    onOpenDisease = vi.fn(),
    onOpenOrganization = vi.fn(),
    onOpenTrial = vi.fn(),
    onOpenDeal = vi.fn(),
    onOpenRegulatoryEvent = vi.fn(),
  }: {
    initialSection?: DrugDossierSection;
    onOpenEntity?: (entityId: string) => void;
    onOpenDrug?: (entityId: string) => void;
    onOpenTarget?: (entityId: string) => void;
    onOpenDisease?: (entityId: string) => void;
    onOpenOrganization?: (entityId: string) => void;
    onOpenTrial?: (trialId: string) => void;
    onOpenDeal?: (dealId: string) => void;
    onOpenRegulatoryEvent?: (eventId: string) => void;
  } = {},
) {
  function Harness() {
    const [activeSection, setActiveSection] = useState<DrugDossierSection>(initialSection);
    const [programOffset, setProgramOffset] = useState(0);
    return (
      <DrugView
        drug={entity}
        activeSection={activeSection}
        programOffset={programOffset}
        onProgramOffsetChange={setProgramOffset}
        onSectionChange={setActiveSection}
        onOpenEntity={onOpenEntity}
        onOpenDrug={onOpenDrug}
        onOpenTarget={onOpenTarget}
        onOpenDisease={onOpenDisease}
        onOpenOrganization={onOpenOrganization}
        onOpenTrial={onOpenTrial}
        onOpenPatent={vi.fn()}
        onOpenDeal={onOpenDeal}
        onOpenRegulatoryEvent={onOpenRegulatoryEvent}
        onOpenNewsEvent={vi.fn()}
      />
    );
  }

  return renderWithQueryClient(<Harness />);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(loadDrugDossier).mockResolvedValue(dossier);
  vi.mocked(loadDrugPrograms).mockResolvedValue(makeProgramPage());
});

it("loads the governed drug dossier and exposes cross-domain overview actions", async () => {
  const onOpenEntity = vi.fn();
  const onOpenTarget = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  renderDrugView(drug, { onOpenEntity, onOpenTarget, onOpenDisease, onOpenOrganization });

  expect(await screen.findByRole("heading", { name: "VX-101" })).toBeInTheDocument();
  expect(loadDrugDossier).toHaveBeenCalledWith("drug-1", expect.any(AbortSignal));
  expect(screen.getByText("药物类型")).toBeInTheDocument();
  expect(screen.getByText("小分子")).toBeInTheDocument();
  expect(screen.queryByText("Modality")).not.toBeInTheDocument();
  expect(screen.queryAllByText(/已确认|已查证/)).toHaveLength(0);
  expect(screen.getByText("II 期临床")).toBeInTheDocument();
  expect(screen.getByText("II 期临床 / I 期临床")).toBeInTheDocument();
  expect(screen.getByLabelText("VX-101 结构图")).toHaveAttribute("data-smiles", "CCO");
  expect(screen.getByText("全球 II 期启动")).toBeInTheDocument();
  expect(screen.getByText("结果可能受数据覆盖范围和来源更新时间影响。")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("target-1");

  fireEvent.click(screen.getByRole("tab", { name: "研发管线（1）" }));
  expect(screen.getByRole("tab", { name: "研发管线（1）" })).toHaveAttribute("aria-selected", "true");
  const progress = screen.getByRole("table", { name: "药物适应症与地区进度" });
  expect(progress).toHaveTextContent("非小细胞肺癌");
  expect(progress).toHaveTextContent("II 期临床");
  expect(progress).toHaveTextContent("I 期临床");
  expect(progress).toHaveTextContent("在研");
  expect(progress).toHaveTextContent("EGFR inhibitor");
  const rights = screen.getByRole("table", { name: "药物研发机构与权益" });
  expect(within(rights).getByRole("columnheader", { name: "药物类型与分类" })).toBeVisible();
  expect(rights).toHaveTextContent("小分子");
  expect(rights).not.toHaveTextContent("small molecule");
  expect(rights).toHaveTextContent("Vector Pharma");
  expect(rights).toHaveTextContent("原研 · 中国 · biopharma");
  expect(rights).toHaveTextContent("Strategic Bio");
  expect(rights).toHaveTextContent("合作研发 · 美国 · biotech");
  expect(rights).toHaveTextContent("全球");
  expect(rights).toHaveTextContent("大中华区");
  expect(rights).toHaveTextContent("First-in-Class");
  expect(rights).toHaveTextContent("化学药");
  expect(rights).toHaveTextContent("2 条阶段与里程碑");
  fireEvent.click(within(progress).getByRole("button", { name: "EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("target-1");

  fireEvent.click(within(progress).getByRole("button", { name: "非小细胞肺癌" }));
  expect(onOpenDisease).toHaveBeenCalledWith("disease-1");
  fireEvent.click(screen.getByRole("button", { name: "Strategic Bio" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("organization-2");
  expect(onOpenEntity).not.toHaveBeenCalled();
});

it("summarizes available sections and exposes program-derived associations", async () => {
  const onOpenTarget = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  renderDrugView(drug, {
    initialSection: "relationships",
    onOpenTarget,
    onOpenDisease,
    onOpenOrganization,
  });

  expect(await screen.findByRole("tab", { name: "研发管线（1）" })).toBeInTheDocument();
  const associations = screen.getByRole("tab", { name: "关联信息（4）" });
  const activities = screen.getByRole("tab", { name: "活性（0）" });
  expect(associations).toHaveAttribute("aria-selected", "true");
  expect(activities).toHaveAttribute("aria-disabled", "true");

  fireEvent.click(activities);
  expect(associations).toHaveAttribute("aria-selected", "true");
  expect(screen.queryByText("暂无关联实体关系")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "靶点、适应症与研发机构" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "EGFR" }));
  fireEvent.click(screen.getByRole("button", { name: "非小细胞肺癌" }));
  fireEvent.click(screen.getByRole("button", { name: "Strategic Bio" }));
  expect(onOpenTarget).toHaveBeenCalledWith("target-1");
  expect(onOpenDisease).toHaveBeenCalledWith("disease-1");
  expect(onOpenOrganization).toHaveBeenCalledWith("organization-2");
});

it("uses public product language for structure and coverage information", async () => {
  vi.mocked(loadDrugDossier).mockResolvedValueOnce({
    ...dossier,
    structures: [],
    coverage: [
      ...dossier.coverage,
      { domain: "relationships", total: 2, returned: 2, status: "available", note: "完整返回" },
      { domain: "evidence", total: 4, returned: 4, status: "available", note: "完整返回" },
    ],
  });
  renderDrugView();

  expect(await screen.findByRole("heading", { name: "各类信息收录情况" })).toBeInTheDocument();
  expect(screen.getByText("暂无结构数据")).toBeInTheDocument();
  expect(screen.getByText("当前数据中未收录可展示的化学结构")).toBeInTheDocument();
  expect(screen.getByText("结果可能受数据覆盖范围和来源更新时间影响。")).toBeInTheDocument();
  const coverageTable = screen.getByRole("table", { name: "药物档案领域数据覆盖" });
  expect(within(coverageTable).getByText("关联信息")).toBeInTheDocument();
  expect(within(coverageTable).getByText("资料来源")).toBeInTheDocument();
  expect(within(coverageTable).getByText("生物活性")).toBeInTheDocument();
  expect(within(coverageTable).getByText("研发项目")).toBeInTheDocument();
  expect(within(coverageTable).queryByText("实体关系")).not.toBeInTheDocument();
  expect(within(coverageTable).queryByText("来源证据")).not.toBeInTheDocument();
  expect(within(coverageTable).queryByText("活性", { exact: true })).not.toBeInTheDocument();
  expect(within(coverageTable).queryByText("研发管线", { exact: true })).not.toBeInTheDocument();
  expect(screen.queryByText("标准化结构")).not.toBeInTheDocument();
  expect(screen.queryByText("覆盖与限制")).not.toBeInTheDocument();
  expect(screen.queryByText("本次返回")).not.toBeInTheDocument();
  expect(screen.queryByText("已返回当前匹配记录")).not.toBeInTheDocument();
});

it("keeps relationship coverage aligned with the associations visible to users", async () => {
  vi.mocked(loadDrugDossier).mockResolvedValueOnce({
    ...dossier,
    relationships: [],
    coverage: [
      ...dossier.coverage,
      {
        domain: "relationships",
        total: 0,
        returned: 0,
        status: "not_observed",
        note: "未观察到直接实体关系",
      },
    ],
  });
  renderDrugView();

  expect(await screen.findByRole("tab", { name: "关联信息（4）" })).toBeInTheDocument();
  const coverageTable = screen.getByRole("table", { name: "药物档案领域数据覆盖" });
  const relationshipsRow = within(coverageTable).getByText("关联信息").closest("tr");
  if (!relationshipsRow) throw new Error("关联信息覆盖行未渲染");
  expect(relationshipsRow).toHaveTextContent("关联信息4可查看");
  expect(relationshipsRow).not.toHaveTextContent("关联信息0暂无记录");
});

it("pages the complete development portfolio instead of stopping at the first page", async () => {
  const secondPageProgram = { ...dossier.programs[0], id: "program-2", disease_name: "第二适应症" };
  vi.mocked(loadDrugPrograms)
    .mockResolvedValueOnce(makeProgramPage(0, [dossier.programs[0]], 233))
    .mockResolvedValueOnce(makeProgramPage(100, [secondPageProgram], 233));

  renderDrugView(drug, { initialSection: "pipeline" });

  expect(await screen.findByRole("heading", { name: /适应症与地区进度/ })).toHaveTextContent("233");
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));

  expect(await screen.findAllByText("第二适应症")).not.toHaveLength(0);
  expect(loadDrugPrograms).toHaveBeenLastCalledWith("drug-1", 100, 100, expect.any(AbortSignal));
});

it("supports legacy program records without optional target and milestone arrays", async () => {
  vi.mocked(loadDrugDossier).mockResolvedValueOnce({
    ...dossier,
    programs: [{ ...dossier.programs[0], targets: undefined, milestones: undefined }],
  });
  renderDrugView();

  expect(await screen.findByRole("button", { name: "EGFR" })).toBeInTheDocument();
  expect(screen.getByText("暂无带日期的研发里程碑")).toBeInTheDocument();
});

it("uses typed navigation for governed drug relationships", async () => {
  const onOpenEntity = vi.fn();
  const onOpenTarget = vi.fn();
  vi.mocked(loadDrugDossier).mockResolvedValueOnce({
    ...dossier,
    relationships: [
      {
        id: "relationship-1",
        direction: "outgoing",
        predicate: "has_target",
        related_entity: {
          id: "target-1",
          canonical_entity_id: "target-1",
          entity_type: "target",
          name: "EGFR",
          description: null,
          external_ids: {},
          attributes: {},
          review_status: "verified",
          created_at: "2026-07-20T08:00:00Z",
          updated_at: "2026-07-25T08:00:00Z",
        },
        review_status: "verified",
        attributes: {},
        valid_from: null,
        valid_to: null,
      },
    ],
  });
  renderDrugView(drug, { initialSection: "relationships", onOpenEntity, onOpenTarget });

  const relationships = await screen.findByRole("table", { name: "关联实体关系" });
  fireEvent.click(within(relationships).getByRole("button", { name: "EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("target-1");
  expect(onOpenEntity).not.toHaveBeenCalled();
});

it("presents linked approved indications before other regulatory events", async () => {
  const onOpenEntity = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenRegulatoryEvent = vi.fn();
  renderDrugView(drug, { initialSection: "regulatory", onOpenEntity, onOpenDisease, onOpenRegulatoryEvent });

  const approvals = await screen.findByRole("table", { name: "药物获批适应症" });
  expect(approvals).toHaveTextContent("非小细胞肺癌");
  expect(approvals).toHaveTextContent("Adults with EGFR-positive non-small cell lung cancer");
  expect(approvals).toHaveTextContent("治疗线次：二线");
  expect(approvals).toHaveTextContent("EGFR exon 20 insertion");
  expect(approvals).toHaveTextContent("剂型：片剂");
  expect(approvals).toHaveTextContent("给药途径：口服");
  expect(approvals).toHaveTextContent("美国");
  expect(approvals).toHaveTextContent("已批准");
  expect(screen.getByText("其他监管事件（0）")).toBeVisible();

  fireEvent.click(screen.getByRole("button", { name: "非小细胞肺癌" }));
  expect(onOpenDisease).toHaveBeenCalledWith("disease-1");
  expect(onOpenEntity).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "打开监管事件详情：VX-101 approved for EGFR-positive NSCLC" }));
  expect(onOpenRegulatoryEvent).toHaveBeenCalledWith("regulatory-1");
});

it("presents governed clinical outcomes, role entities and trial design details", async () => {
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenTarget = vi.fn();
  const onOpenTrial = vi.fn();
  renderDrugView(drug, { initialSection: "trials", onOpenEntity, onOpenDrug, onOpenTarget, onOpenTrial });

  expect(await screen.findByRole("tab", { name: "临床结果与试验（1）" })).toHaveAttribute("aria-selected", "true");
  const results = screen.getByRole("table", { name: "药物临床结果" });
  expect(results).toHaveTextContent("NCT01234567");
  expect(results).toHaveTextContent("EGFR-positive non-small cell lung cancer");
  expect(results).toHaveTextContent("II 期");
  expect(results).toHaveTextContent("二线");
  expect(results).toHaveTextContent("Objective response rate");
  expect(results).toHaveTextContent("VX-101 combination: 68.0 %");
  expect(results).toHaveTextContent("积极");
  expect(results).toHaveTextContent("ASCO 2026");

  const trials = screen.getByRole("table", { name: "药物关联临床试验" });
  expect(trials).toHaveTextContent("已完成");
  expect(trials).toHaveTextContent("IST（申办方发起）");
  expect(trials).toHaveTextContent("VX-101、Carboplatin");
  expect(trials).toHaveTextContent("Vector Pharma");
  expect(trials).toHaveTextContent("184");

  fireEvent.click(screen.getByRole("button", { name: "打开联用药物：Carboplatin" }));
  expect(onOpenDrug).toHaveBeenCalledWith("drug-2");
  fireEvent.click(screen.getByRole("button", { name: "打开试验靶点：EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("target-1");
  expect(onOpenEntity).not.toHaveBeenCalled();
  fireEvent.click(screen.getAllByRole("button", { name: "打开临床试验详情：NCT01234567" })[0]);
  expect(onOpenTrial).toHaveBeenCalledWith("trial-1");
});

it("presents governed deal parties, asset stages and rights without inferring final ownership", async () => {
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenOrganization = vi.fn();
  const onOpenDeal = vi.fn();
  renderDrugView(drug, {
    initialSection: "deals",
    onOpenEntity,
    onOpenDrug,
    onOpenOrganization,
    onOpenDeal,
  });

  const deals = await screen.findByRole("table", { name: "药物关联交易" });
  expect(deals).toHaveTextContent("VX-101 Global License");
  expect(deals).toHaveTextContent("许可 · 2026/06/20");
  expect(deals).toHaveTextContent("进行中");
  expect(deals).toHaveTextContent("对外许可");
  expect(deals).toHaveTextContent("许可方 · 美国 · biopharma");
  expect(deals).toHaveTextContent("被许可方 · 中国 · biotech");
  expect(deals).toHaveTextContent("交易时 II 期临床 · 当前 II 期临床 · 2026/07/24");
  expect(deals).toHaveTextContent("首付款 USD 25.0M");
  expect(deals).toHaveTextContent("潜在总额 USD 500.0M");

  const rights = screen.getByRole("table", { name: "药物交易权益归属" });
  expect(rights).toHaveTextContent("Strategic Bio");
  expect(rights).toHaveTextContent("商业化");
  expect(rights).toHaveTextContent("大中华区");
  expect(rights).toHaveTextContent("独占");
  expect(rights).toHaveTextContent("VX-101 独家商业化权益");

  fireEvent.click(within(deals).getByRole("button", { name: "Vector Pharma" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("organization-1");
  fireEvent.click(within(deals).getByRole("button", { name: "VX-101" }));
  expect(onOpenDrug).toHaveBeenCalledWith(drug.id);
  fireEvent.click(within(rights).getByRole("button", { name: "Strategic Bio" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("organization-2");
  expect(onOpenEntity).not.toHaveBeenCalled();
  fireEvent.click(within(deals).getByRole("button", { name: "VX-101 Global License" }));
  expect(onOpenDeal).toHaveBeenCalledWith("deal-1");
});

it("preserves known deal parties and assets when roles and transaction stages are undisclosed", async () => {
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenOrganization = vi.fn();
  vi.mocked(loadDrugDossier).mockResolvedValueOnce({
    ...dossier,
    deals: dossier.deals.map((deal) => ({ ...deal, party_roles: [], asset_stages: [], rights: [] })),
  });
  renderDrugView(drug, { initialSection: "deals", onOpenEntity, onOpenDrug, onOpenOrganization });

  const deals = await screen.findByRole("table", { name: "药物关联交易" });
  expect(deals).toHaveTextContent("Vector Pharma");
  expect(deals).toHaveTextContent("Strategic Bio");
  expect(deals).toHaveTextContent("角色未披露");
  expect(deals).toHaveTextContent("VX-101");
  expect(deals).toHaveTextContent("交易时阶段未披露");
  expect(screen.getByText("当前关联交易未披露结构化地域权益")).toBeInTheDocument();

  fireEvent.click(within(deals).getByRole("button", { name: "Vector Pharma" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("organization-1");
  fireEvent.click(within(deals).getByRole("button", { name: "VX-101" }));
  expect(onOpenDrug).toHaveBeenCalledWith(drug.id);
  expect(onOpenEntity).not.toHaveBeenCalled();
});

it("fails closed for a non-drug deep link without calling the drug endpoint", () => {
  renderDrugView({ ...drug, entity_type: "target", name: "EGFR" });

  expect(screen.getByText("该深链接不是药物实体，无法打开药物专业档案")).toBeInTheDocument();
  expect(loadDrugDossier).not.toHaveBeenCalled();
});
