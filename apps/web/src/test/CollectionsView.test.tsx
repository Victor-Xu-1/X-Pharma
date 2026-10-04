import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { CollectionComparisonMatrix } from "../components/CollectionComparisonMatrix";
import {
  addComparisonSetMember,
  type CollectionDetail,
  type CollectionEntity,
  type CollectionPolicy,
  exportComparisonSet,
  getComparisonSet,
  getWorkspaceExportPolicy,
  loadCollectionCatalog,
  searchCollectionEntities,
} from "../lib/contracts/collections";
import {
  type DrugComparison,
  type EntityDossier,
  loadDrugComparison,
  loadEntityDossier,
} from "../lib/contracts/entityDossier";
import { downloadBlob } from "../lib/download";
import type { User } from "../lib/types";
import { CollectionsView } from "../views/CollectionsView";

vi.mock("../lib/contracts/collections", () => ({
  collectionsKeys: {
    sets: ["collections", "sets"],
    catalogs: ["collections", "catalog"],
    catalog: (q: string, offset: number) => ["collections", "catalog", q, offset],
    versions: (id: string) => ["collections", "versions", id],
    detail: (id: string) => ["collections", "sets", id],
    policy: ["collections", "export-policy"],
    search: (query: string) => ["collections", "entity-search", query],
  },
  loadCollectionCatalog: vi.fn(),
  listCollectionVersions: vi.fn(async () => []),
  getComparisonSet: vi.fn(),
  getWorkspaceExportPolicy: vi.fn(),
  searchCollectionEntities: vi.fn(),
  createComparisonSet: vi.fn(),
  updateComparisonSet: vi.fn(),
  addComparisonSetMember: vi.fn(),
  removeComparisonSetMember: vi.fn(),
  saveWorkspaceExportPolicy: vi.fn(),
  exportComparisonSet: vi.fn(),
}));
vi.mock("../lib/download", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/download")>();
  return { ...actual, downloadBlob: vi.fn() };
});
vi.mock("../lib/contracts/entityDossier", () => ({
  entityDossierKeys: {
    detail: (entityId: string) => ["entity-dossier", entityId],
    drugComparison: (entityIds: string[]) => ["drug-comparison", ...entityIds],
  },
  loadDrugComparison: vi.fn(),
  loadEntityDossier: vi.fn(),
}));

const user: User = {
  id: "user-1",
  tenant_id: "tenant-1",
  email: "admin@example.test",
  display_name: "Admin",
  role: "admin",
};
const entity: CollectionEntity = {
  id: "11111111-1111-4111-8111-111111111111",
  canonical_entity_id: "11111111-1111-4111-8111-111111111111",
  entity_type: "target",
  name: "EGFR",
  description: "Epidermal growth factor receptor",
  external_ids: { uniprot: "P00533" },
  attributes: {},
  review_status: "verified",
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T10:00:00Z",
};
const company: CollectionEntity = {
  ...entity,
  id: "33333333-3333-4333-8333-333333333333",
  canonical_entity_id: "33333333-3333-4333-8333-333333333333",
  entity_type: "organization",
  name: "Example Biopharma",
  description: "Clinical-stage biotechnology company",
  external_ids: { lei: "EXAMPLE-LEI" },
};
const drugA: CollectionEntity = {
  ...entity,
  id: "44444444-4444-4444-8444-444444444444",
  canonical_entity_id: "44444444-4444-4444-8444-444444444444",
  entity_type: "drug",
  name: "Drug A",
  description: "IFNA2 therapy A",
  external_ids: { pharmcube_npuid: "DR-A" },
};
const drugB: CollectionEntity = {
  ...drugA,
  id: "55555555-5555-4555-8555-555555555555",
  canonical_entity_id: "55555555-5555-4555-8555-555555555555",
  name: "Drug B",
  description: "IFNA2 therapy B",
  external_ids: { pharmcube_npuid: "DR-B" },
};
const emptySet: CollectionDetail = {
  id: "22222222-2222-4222-8222-222222222222",
  owner_user_id: user.id,
  name: "EGFR landscape",
  description: "",
  visibility: "private",
  version: 1,
  member_count: 0,
  editable: true,
  members: [],
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T10:00:00Z",
};
const populatedSet: CollectionDetail = {
  ...emptySet,
  version: 2,
  member_count: 1,
  members: [
    {
      id: "member-1",
      position: 0,
      added_by_user_id: user.id,
      created_at: "2026-07-18T10:00:00Z",
      entity,
    },
  ],
};
const comparisonSet: CollectionDetail = {
  ...emptySet,
  version: 3,
  member_count: 2,
  members: [
    {
      id: "member-1",
      position: 0,
      added_by_user_id: user.id,
      created_at: "2026-07-18T10:00:00Z",
      entity,
    },
    {
      id: "member-2",
      position: 1,
      added_by_user_id: user.id,
      created_at: "2026-07-18T10:00:00Z",
      entity: company,
    },
  ],
};
const coverageDomains: EntityDossier["coverage"][number]["domain"][] = [
  "relationships",
  "evidence",
  "activities",
  "programs",
  "clinical_trials",
  "patents",
  "deals",
  "regulatory_events",
  "news_events",
  "structures",
  "target_evidence",
];

function dossierFor(subject: CollectionEntity, programCount: number): EntityDossier {
  return {
    entity: subject,
    relationships: [],
    activities: [],
    programs: [],
    clinical_trials: [],
    patents: [],
    deals: [],
    regulatory_events: [],
    news_events: [],
    structures: [],
    target_evidence: [],
    coverage: coverageDomains.map((domain) => ({
      domain,
      total: domain === "programs" ? programCount : 0,
      returned: domain === "programs" ? programCount : 0,
      status: domain === "programs" ? "available" : "not_observed",
      note: domain === "programs" ? "完整授权命中集" : "当前许可来源未观察到记录",
    })),
    as_of: "2026-07-18T10:00:00Z",
    warnings: [],
  };
}

function drugComparisonFor(
  first: CollectionEntity,
  second: CollectionEntity,
  options: {
    firstProgramCount?: number;
  },
): DrugComparison {
  return {
    query_schema_version: "pharma.drug.comparison.v1",
    as_of: "2026-08-11T00:00:00Z",
    items: [
      {
        entity: first,
        target_names: ["IFNA2"],
        indication_names: Array.from({ length: options.firstProgramCount ?? 1 }, (_, index) =>
          index ? `适应症 ${index + 1}` : "慢性丙肝",
        ),
        organization_names: ["Company A"],
        program_status_counts: { active: options.firstProgramCount ?? 1 },
        summary: {
          program_count: options.firstProgramCount ?? 1,
          target_count: 1,
          indication_count: options.firstProgramCount ?? 1,
          organization_count: 1,
          modalities: ["biologic"],
          highest_phase: "approved",
          highest_global_phase: "approved",
          highest_china_phase: "phase_3",
          latest_status_date: "2026-08-11T00:00:00Z",
        },
        as_of: "2026-08-11T00:00:00Z",
      },
      {
        entity: second,
        target_names: ["IFNA2"],
        indication_names: ["黑色素瘤"],
        organization_names: ["Company B"],
        program_status_counts: { inactive: 1 },
        summary: {
          program_count: 1,
          target_count: 1,
          indication_count: 1,
          organization_count: 1,
          modalities: ["biologic"],
          highest_phase: "phase_2",
          highest_global_phase: "phase_2",
          highest_china_phase: "phase_1",
          latest_status_date: "2026-08-10T00:00:00Z",
        },
        as_of: "2026-08-11T00:00:00Z",
      },
    ],
  };
}
const policy: CollectionPolicy = {
  id: "policy-1",
  policy_version: "workspace-export-v1",
  enabled: true,
  allowed_formats: ["json", "xlsx"],
  allowed_fields: ["position", "id", "entity_type", "name", "external_ids", "review_status"],
  max_records_per_export: 20,
  attribution: "Internal use",
  configured_by_user_id: user.id,
  policy_sha256: "a".repeat(64),
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T10:00:00Z",
};

function renderView({
  activeCollectionId = null,
  comparedEntityIds = [],
  onLocationChange = vi.fn(),
  onOpenEntity = vi.fn(),
}: {
  activeCollectionId?: string | null;
  comparedEntityIds?: string[];
  onLocationChange?: (collectionId: string | null, entityIds: string[], replace?: boolean) => void;
  onOpenEntity?: (entity: CollectionEntity) => void;
} = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <CollectionsView
        activeCollectionId={activeCollectionId}
        comparedEntityIds={comparedEntityIds}
        onLocationChange={onLocationChange}
        onOpenEntity={onOpenEntity}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(loadCollectionCatalog).mockResolvedValue({
    items: [emptySet],
    total: [emptySet].length,
    limit: 25,
    offset: 0,
  });
  vi.mocked(getComparisonSet).mockResolvedValue(emptySet);
  vi.mocked(getWorkspaceExportPolicy).mockResolvedValue(policy);
  vi.mocked(searchCollectionEntities).mockResolvedValue({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [],
    items: [entity],
    total: 1,
    limit: 25,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: {},
    suggestions: [],
    engine: "database",
    took_ms: 1,
  });
  vi.mocked(addComparisonSetMember).mockResolvedValue(populatedSet);
  vi.mocked(exportComparisonSet).mockResolvedValue(new Blob(["{}"], { type: "application/json" }));
  vi.mocked(loadEntityDossier).mockImplementation(async (entityId) =>
    entityId === entity.id ? dossierFor(entity, 3) : dossierFor(company, 1),
  );
  vi.mocked(loadDrugComparison).mockResolvedValue(drugComparisonFor(drugA, drugB, {}));
});

it("builds a version-governed comparison set and downloads a bounded standard export", async () => {
  renderView();
  await waitFor(() => expect(screen.getAllByText("EGFR landscape")).toHaveLength(2));
  expect(screen.queryByText("工作台导出策略")).not.toBeInTheDocument();
  expect(screen.queryByText("租户导出策略")).not.toBeInTheDocument();
  expect(await screen.findByRole("checkbox", { name: "记录编号" })).toBeDisabled();
  expect(screen.queryByRole("checkbox", { name: "审核状态" })).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("搜索要加入的药物、靶点、机构或适应症"), {
    target: { value: "EGFR" },
  });
  fireEvent.click(screen.getByRole("button", { name: "检索" }));
  fireEvent.click(await screen.findByRole("button", { name: "加入 EGFR" }));

  await waitFor(() =>
    expect(addComparisonSetMember).toHaveBeenCalledWith(emptySet.id, {
      entity_id: entity.id,
      expected_version: 1,
    }),
  );
  expect(await screen.findByText("Epidermal growth factor receptor")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "导出" }));
  await waitFor(() => expect(exportComparisonSet).toHaveBeenCalledOnce());
  expect(exportComparisonSet).toHaveBeenCalledWith(
    emptySet.id,
    expect.objectContaining({
      expected_version: 2,
      export_format: "json",
      fields: expect.arrayContaining(["id", "entity_type", "name"]),
    }),
  );
  expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), `comparison-${emptySet.id}-v2.json`);
});

it("compares two governed dossiers from a stable collection selection", async () => {
  vi.mocked(loadCollectionCatalog).mockResolvedValue({
    items: [comparisonSet],
    total: [comparisonSet].length,
    limit: 25,
    offset: 0,
  });
  vi.mocked(getComparisonSet).mockResolvedValue(comparisonSet);
  const onLocationChange = vi.fn();
  const onOpenEntity = vi.fn();
  renderView({
    activeCollectionId: comparisonSet.id,
    comparedEntityIds: [entity.id, company.id],
    onLocationChange,
    onOpenEntity,
  });

  const matrix = await screen.findByRole("table", { name: "研发情报对比表" });
  expect(within(matrix).getByRole("columnheader", { name: /EGFR/ })).toBeInTheDocument();
  expect(within(matrix).getByRole("columnheader", { name: /Example Biopharma/ })).toBeInTheDocument();
  expect(screen.queryAllByText("审核状态")).toHaveLength(0);
  expect(screen.queryAllByText(/已确认|已查证/)).toHaveLength(0);
  expect(screen.queryByText("private")).not.toBeInTheDocument();
  expect(screen.queryByText(/v3/)).not.toBeInTheDocument();
  expect(screen.queryByText("数据来自同一权限边界下的实时专业档案")).not.toBeInTheDocument();
  expect(screen.getByText("仅自己可见")).toBeInTheDocument();
  expect(screen.getByText("根据当前可查看的信息实时生成")).toBeInTheDocument();
  expect(screen.queryByText(policy.policy_version)).not.toBeInTheDocument();
  expect(within(matrix).queryByText(entity.id)).not.toBeInTheDocument();
  expect(within(matrix).queryByText(company.id)).not.toBeInTheDocument();
  expect(within(matrix).getByText("资料编号")).toBeInTheDocument();
  expect(within(matrix).getByText("关联信息")).toBeInTheDocument();
  expect(within(matrix).getByText("资料来源")).toBeInTheDocument();
  expect(within(matrix).queryByText("外部标识")).not.toBeInTheDocument();
  expect(within(matrix).queryByText("原始证据")).not.toBeInTheDocument();
  const programsRow = within(matrix).getByText("研发项目").closest("tr");
  if (!programsRow) throw new Error("研发项目比较行未渲染");
  expect(within(programsRow).getByText("3")).toBeInTheDocument();
  expect(within(programsRow).getByText("1")).toBeInTheDocument();

  fireEvent.click(within(matrix).getByRole("button", { name: "打开 EGFR 详情" }));
  expect(onOpenEntity).toHaveBeenCalledWith(entity);

  fireEvent.click(screen.getByRole("checkbox", { name: "纳入情报对比：EGFR" }));
  expect(onLocationChange).toHaveBeenLastCalledWith(comparisonSet.id, [company.id], true);
});

it("compares drug development dimensions instead of only generic coverage counts", async () => {
  vi.mocked(loadDrugComparison).mockResolvedValue(drugComparisonFor(drugA, drugB, { firstProgramCount: 105 }));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <CollectionComparisonMatrix entities={[drugA, drugB]} onOpenEntity={vi.fn()} />
    </QueryClientProvider>,
  );

  const matrix = await screen.findByRole("table", { name: "研发情报对比表" });
  expect(within(matrix).getByText("研发格局")).toBeInTheDocument();
  expect(loadDrugComparison).toHaveBeenCalledWith([drugA.id, drugB.id], expect.any(AbortSignal));
  expect(loadEntityDossier).not.toHaveBeenCalled();
  expect(within(matrix).getAllByText("IFNA2")).toHaveLength(2);
  const indicationsRow = within(matrix).getByText("适应症", { exact: true }).closest("tr");
  if (!indicationsRow) throw new Error("适应症聚合行未渲染");
  expect(indicationsRow).toHaveTextContent("慢性丙肝");
  expect(indicationsRow).toHaveTextContent("等 105 项");
  expect(within(matrix).getByText("黑色素瘤")).toBeInTheDocument();
  expect(within(matrix).getAllByText("已批准").length).toBeGreaterThan(0);
  expect(within(matrix).getAllByText("II期").length).toBeGreaterThan(0);
  expect(within(matrix).getByText("Company A")).toBeInTheDocument();
  expect(within(matrix).getByText("Company B")).toBeInTheDocument();
  expect(within(matrix).getByText("在研（105）")).toBeInTheDocument();
  expect(within(matrix).getByText("已停止（1）")).toBeInTheDocument();
  const programsRow = within(matrix).getByText("研发项目").closest("tr");
  if (!programsRow) throw new Error("研发项目聚合行未渲染");
  expect(within(programsRow).getByText("105")).toBeInTheDocument();
  const identifiersRow = within(matrix).getByText("资料编号").closest("tr");
  if (!identifiersRow) throw new Error("资料编号比较行未渲染");
  expect(identifiersRow).toHaveTextContent("未披露");
  expect(identifiersRow).not.toHaveTextContent(/pharmcube_npuid|DR-A|DR-B/);
});

it("uses public drug terminology and database identifiers in the comparison matrix", async () => {
  const first = {
    ...drugA,
    external_ids: { chembl: "CHEMBL2105719", source_record_id: "internal-drug-a" },
  };
  const second = {
    ...drugB,
    external_ids: { chembl: "CHEMBL3353410", ingestion_record_id: "internal-drug-b" },
  };
  const comparison = drugComparisonFor(first, second, {});
  comparison.items = comparison.items.map((item) => ({
    ...item,
    summary: { ...item.summary, modalities: ["Small molecule"] },
  }));
  vi.mocked(loadDrugComparison).mockResolvedValue(comparison);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <CollectionComparisonMatrix entities={[first, second]} onOpenEntity={vi.fn()} />
    </QueryClientProvider>,
  );

  const matrix = await screen.findByRole("table", { name: "研发情报对比表" });
  expect(within(matrix).getByText("ChEMBL · CHEMBL2105719")).toBeInTheDocument();
  expect(within(matrix).getByText("ChEMBL · CHEMBL3353410")).toBeInTheDocument();
  expect(within(matrix).getAllByText("小分子")).toHaveLength(2);
  expect(matrix).not.toHaveTextContent(/chembl:|INHIBITOR|source_record_id|ingestion_record_id/i);
});

it("explains an undisclosed drug program status without exposing a raw count", async () => {
  const comparison = drugComparisonFor(drugA, drugB, { firstProgramCount: 1 });
  comparison.items[0].program_status_counts = { unknown: 1 };
  vi.mocked(loadDrugComparison).mockResolvedValue(comparison);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <CollectionComparisonMatrix entities={[drugA, drugB]} onOpenEntity={vi.fn()} />
    </QueryClientProvider>,
  );

  const matrix = await screen.findByRole("table", { name: "研发情报对比表" });
  expect(within(matrix).getByText("暂未披露（1）")).toBeInTheDocument();
  expect(within(matrix).queryByText("状态未披露 1")).not.toBeInTheDocument();
});

it("keeps a comparison checkbox checked while URL state catches up", async () => {
  vi.mocked(loadCollectionCatalog).mockResolvedValue({
    items: [comparisonSet],
    total: [comparisonSet].length,
    limit: 25,
    offset: 0,
  });
  vi.mocked(getComparisonSet).mockResolvedValue(comparisonSet);
  const onLocationChange = vi.fn();
  renderView({ activeCollectionId: comparisonSet.id, onLocationChange });

  const checkbox = await screen.findByRole("checkbox", { name: "纳入情报对比：EGFR" });
  fireEvent.click(checkbox);

  expect(checkbox).toBeChecked();
  expect(onLocationChange).toHaveBeenLastCalledWith(comparisonSet.id, [entity.id], true);
});

it("renders the comparison matrix from the optimistic selection before the URL catches up", async () => {
  vi.mocked(loadCollectionCatalog).mockResolvedValue({
    items: [comparisonSet],
    total: [comparisonSet].length,
    limit: 25,
    offset: 0,
  });
  vi.mocked(getComparisonSet).mockResolvedValue(comparisonSet);
  const onLocationChange = vi.fn();
  renderView({
    activeCollectionId: comparisonSet.id,
    comparedEntityIds: [entity.id],
    onLocationChange,
  });

  fireEvent.click(await screen.findByRole("checkbox", { name: "纳入情报对比：Example Biopharma" }));

  const matrix = await screen.findByRole("table", { name: "研发情报对比表" });
  expect(within(matrix).getByRole("columnheader", { name: /EGFR/ })).toBeInTheDocument();
  expect(within(matrix).getByRole("columnheader", { name: /Example Biopharma/ })).toBeInTheDocument();
  expect(onLocationChange).toHaveBeenLastCalledWith(comparisonSet.id, [entity.id, company.id], true);
});
it("keeps the four-entity limit operable and explains how to recover", async () => {
  const additionalEntities = [
    {
      ...entity,
      id: "44444444-4444-4444-8444-444444444444",
      canonical_entity_id: "44444444-4444-4444-8444-444444444444",
      entity_type: "drug" as const,
      name: "Example inhibitor",
    },
    {
      ...entity,
      id: "55555555-5555-4555-8555-555555555555",
      canonical_entity_id: "55555555-5555-4555-8555-555555555555",
      entity_type: "disease" as const,
      name: "Example disease",
    },
    {
      ...entity,
      id: "66666666-6666-4666-8666-666666666666",
      canonical_entity_id: "66666666-6666-4666-8666-666666666666",
      entity_type: "technology" as const,
      name: "Example platform",
    },
  ];
  const cappedSet: CollectionDetail = {
    ...comparisonSet,
    member_count: 5,
    members: [entity, company, ...additionalEntities].map((memberEntity, index) => ({
      id: `member-${index + 1}`,
      position: index,
      added_by_user_id: user.id,
      created_at: "2026-07-18T10:00:00Z",
      entity: memberEntity,
    })),
  };
  vi.mocked(loadCollectionCatalog).mockResolvedValue({
    items: [cappedSet],
    total: [cappedSet].length,
    limit: 25,
    offset: 0,
  });
  vi.mocked(getComparisonSet).mockResolvedValue(cappedSet);
  vi.mocked(loadEntityDossier).mockImplementation(async (entityId) => {
    const matchedEntity = cappedSet.members.find((member) => member.entity.id === entityId)?.entity;
    if (!matchedEntity) throw new Error("测试实体不存在");
    return dossierFor(matchedEntity, 0);
  });
  const onLocationChange = vi.fn();
  renderView({
    activeCollectionId: cappedSet.id,
    comparedEntityIds: cappedSet.members.slice(0, 4).map((member) => member.entity.id),
    onLocationChange,
  });

  const fifthCheckbox = await screen.findByRole("checkbox", { name: "纳入情报对比：Example platform" });
  expect(fifthCheckbox).toBeEnabled();
  expect(fifthCheckbox).toHaveAccessibleDescription("已达到上限，请先取消一个已选条目");
  fireEvent.click(fifthCheckbox);

  expect(await screen.findByRole("alert")).toHaveTextContent("并排比较最多选择 4 个条目，请先取消一个已选条目");
  expect(onLocationChange).not.toHaveBeenCalled();
});

it("surfaces a dossier failure and retries the complete comparison", async () => {
  vi.mocked(loadCollectionCatalog).mockResolvedValue({
    items: [comparisonSet],
    total: [comparisonSet].length,
    limit: 25,
    offset: 0,
  });
  vi.mocked(getComparisonSet).mockResolvedValue(comparisonSet);
  vi.mocked(loadEntityDossier).mockImplementation(async (entityId) => {
    if (entityId === company.id) throw new Error("该实体档案暂不可访问");
    return dossierFor(entity, 3);
  });
  renderView({
    activeCollectionId: comparisonSet.id,
    comparedEntityIds: [entity.id, company.id],
  });

  const failure = await screen.findByRole("alert");
  expect(failure).toHaveTextContent("Example Biopharma：该实体档案暂不可访问");
  vi.mocked(loadEntityDossier).mockImplementation(async (entityId) =>
    entityId === entity.id ? dossierFor(entity, 3) : dossierFor(company, 1),
  );
  fireEvent.click(within(failure).getByRole("button", { name: "重试" }));

  expect(await screen.findByRole("table", { name: "研发情报对比表" })).toBeInTheDocument();
});
