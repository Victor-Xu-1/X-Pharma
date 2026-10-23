import type { DataSource } from "../../lib/contracts/dataFactory";
import type { DataSourceCreate } from "../../lib/generated/models/DataSourceCreate";
import { SourceDraftValidationError } from "./sourceDraftValidation";

export const PUBLIC_RESEARCH_SOURCES = {
  pubmed: {
    rootUri: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
    authorizationScope: "public:ncbi-pubmed-metadata",
  },
  clinicaltrials_gov: {
    rootUri: "https://clinicaltrials.gov/api/v2/studies",
    authorizationScope: "public:clinicaltrials-gov",
  },
  chembl: {
    rootUri: "https://www.ebi.ac.uk/chembl/api/data/",
    authorizationScope: "public:chembl",
  },
} as const;

type PublicResearchSourceType = keyof typeof PUBLIC_RESEARCH_SOURCES;
export type ClinicalTrialsSort =
  | "LastUpdatePostDate:asc"
  | "LastUpdatePostDate:desc"
  | "StudyFirstPostDate:asc"
  | "StudyFirstPostDate:desc";

export function clinicalTrialsSort(value: unknown): ClinicalTrialsSort {
  if (
    value === "LastUpdatePostDate:asc" ||
    value === "LastUpdatePostDate:desc" ||
    value === "StudyFirstPostDate:asc" ||
    value === "StudyFirstPostDate:desc"
  ) {
    return value;
  }
  return "LastUpdatePostDate:desc";
}

export function isPublicResearchSource(sourceType: DataSource["source_type"]): sourceType is PublicResearchSourceType {
  return Object.hasOwn(PUBLIC_RESEARCH_SOURCES, sourceType);
}

export function sourceRequiresCredential(sourceType: DataSource["source_type"]): boolean {
  return ["http_manifest", "s3_snapshot", "sftp_snapshot", "smb_snapshot"].includes(sourceType);
}

export function toLocalDateTimeInput(value?: string | null): string {
  if (value === null) return "";
  const date = value === undefined ? new Date() : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export type PublicSourceDraft = {
  queryTerm: string;
  targetChemblId: string;
  maxRecords: number;
  pageSize: number;
  includeAbstract: boolean;
  includeActivities: boolean;
  activityLimit: number;
  clinicalSort: ClinicalTrialsSort;
  syncMode: "snapshot" | "continuous";
  startDate: string;
  windowDays: number;
  overlapDays: number;
  reconcileIntervalDays: number;
};

export function initialPublicSourceDraft(source?: DataSource): PublicSourceDraft {
  const rule = source?.routing_rules[0] as Record<string, unknown> | undefined;
  return {
    queryTerm: typeof rule?.query_term === "string" ? rule.query_term : "",
    targetChemblId: typeof rule?.target_chembl_id === "string" ? rule.target_chembl_id : "",
    maxRecords: typeof rule?.max_records === "number" ? rule.max_records : 100,
    pageSize: typeof rule?.page_size === "number" ? rule.page_size : 100,
    includeAbstract: rule?.include_abstract === true,
    includeActivities: rule?.include_activities === true,
    activityLimit: typeof rule?.activity_limit === "number" ? rule.activity_limit : 10,
    clinicalSort: clinicalTrialsSort(rule?.sort),
    syncMode: source ? (rule?.sync_mode === "continuous" ? "continuous" : "snapshot") : "continuous",
    startDate: typeof rule?.start_date === "string" ? rule.start_date : new Date().toISOString().slice(0, 10),
    windowDays: typeof rule?.window_days === "number" ? rule.window_days : 31,
    overlapDays: typeof rule?.overlap_days === "number" ? rule.overlap_days : 2,
    reconcileIntervalDays: typeof rule?.reconcile_interval_days === "number" ? rule.reconcile_interval_days : 30,
  };
}

export function sourceRoutingRules(
  sourceType: DataSource["source_type"],
  draft: PublicSourceDraft,
): NonNullable<DataSourceCreate["routing_rules"]> {
  if (!isPublicResearchSource(sourceType)) return [];
  if (!Number.isInteger(draft.maxRecords) || draft.maxRecords < 1 || draft.maxRecords > 1000) {
    throw new SourceDraftValidationError("单批记录数必须是 1–1000 的整数");
  }
  const maxPage = sourceType === "pubmed" ? 200 : sourceType === "chembl" ? 100 : 1000;
  if (!Number.isInteger(draft.pageSize) || draft.pageSize < 1 || draft.pageSize > maxPage) {
    throw new SourceDraftValidationError("每页请求数量必须是 1–{maximum} 的整数", { maximum: maxPage });
  }
  const budget = { max_records: draft.maxRecords, page_size: draft.pageSize };
  if (sourceType === "chembl") {
    if (draft.includeActivities && draft.maxRecords > 25)
      throw new SourceDraftValidationError("活性补充每批最多 25 条机制记录");
    const targetId = draft.targetChemblId.trim().toUpperCase();
    if (!/^CHEMBL[0-9]+$/.test(targetId)) throw new SourceDraftValidationError("请填写有效的 ChEMBL 靶点编号");
    if (!Number.isInteger(draft.activityLimit) || draft.activityLimit < 1 || draft.activityLimit > 10) {
      throw new SourceDraftValidationError("每个药物的活性样本上限必须是 1–10 的整数");
    }
    return [
      {
        ...budget,
        target_chembl_id: targetId,
        sync_mode: draft.syncMode,
        ...(draft.includeActivities ? { include_activities: true, activity_limit: draft.activityLimit } : {}),
      },
    ];
  }
  const query = draft.queryTerm.trim();
  if (!query) throw new SourceDraftValidationError("检索主题不能为空");
  if (sourceType === "pubmed") {
    return [{ ...budget, query_term: query, include_abstract: draft.includeAbstract }];
  }
  if (
    draft.syncMode === "continuous" &&
    (!/^\d{4}-\d{2}-\d{2}$/.test(draft.startDate) ||
      Number.isNaN(new Date(draft.startDate).getTime()) ||
      new Date(draft.startDate).toISOString().slice(0, 10) !== draft.startDate)
  ) {
    throw new SourceDraftValidationError("持续同步需要明确的历史起始日期");
  }
  if (!Number.isInteger(draft.windowDays) || draft.windowDays < 1 || draft.windowDays > 366)
    throw new SourceDraftValidationError("日期分区必须是 1–366 天的整数");
  if (!Number.isInteger(draft.overlapDays) || draft.overlapDays < 1 || draft.overlapDays > 30)
    throw new SourceDraftValidationError("更新回看必须是 1–30 天的整数");
  if (
    !Number.isInteger(draft.reconcileIntervalDays) ||
    draft.reconcileIntervalDays < 1 ||
    draft.reconcileIntervalDays > 365
  )
    throw new SourceDraftValidationError("完整复核周期必须是 1–365 天的整数");
  return [
    {
      ...budget,
      query_term: query,
      sort: draft.clinicalSort,
      sync_mode: draft.syncMode,
      start_date: draft.syncMode === "continuous" ? draft.startDate : null,
      window_days: draft.windowDays,
      overlap_days: draft.overlapDays,
      reconcile_interval_days: draft.reconcileIntervalDays,
    },
  ];
}
