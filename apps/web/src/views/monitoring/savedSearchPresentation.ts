import type { SavedSearch } from "../../lib/contracts/monitoring";
import type {
  ChemistrySavedSearchQuery,
  ClinicalTrialSavedSearchQuery,
  DealSavedSearchQuery,
  EntitySearchQuery,
  EntityType,
  EpidemiologySavedSearchQuery,
  NewsSavedSearchQuery,
  PatentSavedSearchQuery,
  PipelineSavedSearchQuery,
  RegulatorySavedSearchQuery,
} from "../../lib/generated";

const entityTypeLabels: Record<EntityType, string> = {
  drug: "药物",
  target: "靶点",
  disease: "疾病",
  organization: "机构",
  clinical_trial: "临床试验",
  patent: "专利",
  transaction: "交易",
  product: "产品",
  technology: "技术",
  person: "人员",
};
const entityTypeOrder: readonly EntityType[] = [
  "drug",
  "target",
  "disease",
  "organization",
  "clinical_trial",
  "patent",
  "transaction",
  "product",
  "technology",
  "person",
];

type SavedSearchPresentation = { display_mode?: string; analysis_view?: string };
type SavedSearchConditionKind = "text" | "date" | "boolean" | "entity" | "list" | "enum";
type SavedSearchConditionField = { key: string; label: string; kind?: SavedSearchConditionKind };
type SavedSearchSummary = { query: string; type: string; view: string; conditions: string[] };

const savedSearchConditionFields: Record<string, readonly SavedSearchConditionField[]> = {
  pipeline_search: [
    { key: "target_entity_id", label: "靶点", kind: "entity" },
    { key: "target_combination_key", label: "靶点组合", kind: "entity" },
    { key: "disease_entity_id", label: "适应症", kind: "entity" },
    { key: "organization_entity_id", label: "研发机构", kind: "entity" },
    { key: "modality", label: "模态", kind: "list" },
    { key: "drug_category", label: "药品类别", kind: "list" },
    { key: "innovation_type", label: "创新类型", kind: "list" },
    { key: "program_tag", label: "项目标签", kind: "list" },
    { key: "phase", label: "最高阶段" },
    { key: "global_phase", label: "全球阶段" },
    { key: "china_phase", label: "中国阶段" },
    { key: "program_status", label: "项目状态" },
    { key: "organization_role", label: "机构角色" },
    { key: "organization_type", label: "机构类型" },
    { key: "organization_country_region", label: "机构所在地区", kind: "text" },
    { key: "development_rights_region", label: "研发权益地区", kind: "text" },
    { key: "commercialization_rights_region", label: "商业化权益地区", kind: "text" },
    { key: "analysis_dimension", label: "分析维度" },
    { key: "analysis_limit", label: "分析范围" },
    { key: "analysis_stage_scope", label: "阶段口径" },
    { key: "target_aggregation", label: "靶点聚合" },
    { key: "has_clinical_results", label: "临床结果", kind: "boolean" },
    { key: "has_deal", label: "交易记录", kind: "boolean" },
    { key: "global_phase_started_from", label: "全球阶段起始", kind: "date" },
    { key: "global_phase_started_to", label: "全球阶段截止", kind: "date" },
  ],
  clinical_trial_search: [
    { key: "registry", label: "注册平台", kind: "text" },
    { key: "status", label: "试验状态" },
    { key: "phase", label: "临床分期" },
    { key: "study_type", label: "研究类型" },
    { key: "acronym", label: "试验简称", kind: "text" },
    { key: "initiation_type", label: "发起类型" },
    { key: "therapy_line", label: "治疗线次" },
    { key: "has_results", label: "结果披露", kind: "boolean" },
    { key: "result_evaluation", label: "结果评价" },
    { key: "investigational_drug_entity_ids", label: "试验药物", kind: "entity" },
    { key: "combination_drug_entity_ids", label: "联用药物", kind: "entity" },
    { key: "investigational_target_entity_ids", label: "试验靶点", kind: "entity" },
    { key: "combination_target_entity_ids", label: "联用靶点", kind: "entity" },
    { key: "publication_id", label: "发表编号", kind: "text" },
    { key: "conference", label: "会议", kind: "text" },
    { key: "results_posted_from", label: "结果发布日期起", kind: "date" },
    { key: "results_posted_to", label: "结果发布日期止", kind: "date" },
  ],
  patent_search: [
    { key: "applicant", label: "申请人", kind: "text" },
    { key: "legal_status", label: "法律状态" },
    { key: "entity_id", label: "关联实体", kind: "entity" },
    { key: "priority_from", label: "优先权日起", kind: "date" },
    { key: "priority_to", label: "优先权日止", kind: "date" },
    { key: "expiration_from", label: "到期日起", kind: "date" },
    { key: "expiration_to", label: "到期日止", kind: "date" },
  ],
  deal_search: [
    { key: "deal_type", label: "交易类型" },
    { key: "status", label: "交易状态" },
    { key: "direction", label: "交易方向" },
    { key: "territory", label: "权益地区", kind: "text" },
    { key: "party", label: "参与机构", kind: "text" },
    { key: "party_entity_id", label: "参与机构实体", kind: "entity" },
    { key: "party_role", label: "参与角色" },
    { key: "asset_entity_id", label: "交易资产", kind: "entity" },
    { key: "asset_modality", label: "资产模态", kind: "list" },
    { key: "development_phase_at_transaction", label: "交易时阶段" },
    { key: "current_development_phase", label: "当前最高阶段" },
    { key: "right_type", label: "权益类型" },
    { key: "currency", label: "币种", kind: "text" },
    { key: "announced_from", label: "初始披露日起", kind: "date" },
    { key: "announced_to", label: "初始披露日止", kind: "date" },
  ],
  regulatory_search: [
    { key: "agency", label: "监管机构", kind: "text" },
    { key: "jurisdiction", label: "辖区", kind: "text" },
    { key: "event_type", label: "事件类型" },
    { key: "status", label: "事件状态" },
    { key: "designation_type", label: "认定资格" },
    { key: "label_change_type", label: "标签变更" },
    { key: "safety_signal_type", label: "安全信号" },
    { key: "safety_severity", label: "严重程度" },
    { key: "safety_status", label: "信号状态" },
    { key: "has_boxed_warning", label: "黑框警告", kind: "boolean" },
    { key: "decision_from", label: "决定日起", kind: "date" },
    { key: "decision_to", label: "决定日止", kind: "date" },
  ],
  epidemiology_search: [
    { key: "disease_entity_id", label: "疾病", kind: "entity" },
    { key: "patient_population_id", label: "患者人群", kind: "entity" },
    { key: "measure", label: "指标" },
    { key: "geography", label: "地区", kind: "text" },
    { key: "population_scope", label: "人群口径", kind: "text" },
    { key: "age_group", label: "年龄", kind: "text" },
    { key: "sex", label: "性别", kind: "text" },
    { key: "unit", label: "单位", kind: "text" },
    { key: "period_start_from", label: "观测期起", kind: "date" },
    { key: "period_end_to", label: "观测期止", kind: "date" },
  ],
  news_search: [
    { key: "event_type", label: "事件类型" },
    { key: "publisher", label: "发布方", kind: "text" },
    { key: "venue", label: "会议/期刊", kind: "text" },
    { key: "language", label: "语言", kind: "text" },
    { key: "content_scope", label: "研究范围", kind: "text" },
    { key: "entity_id", label: "关联实体", kind: "entity" },
    { key: "published_from", label: "发布日期起", kind: "date" },
    { key: "published_to", label: "发布日期止", kind: "date" },
  ],
};

function savedSearchView(query: SavedSearchPresentation): string {
  if (query.display_mode === "timeline") return "时间线";
  if (query.display_mode === "landscape") return query.analysis_view === "table" ? "统计表" : "统计图";
  return "列表";
}

function savedSearchConditionValue(value: unknown, kind: SavedSearchConditionKind = "enum"): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (Array.isArray(value)) {
    if (!value.length) return null;
    if (kind === "entity") return value.length === 1 ? "已选" : `已选${value.length}项`;
    if (kind === "list") return value.length === 1 ? "已设置" : `已设置${value.length}项`;
    return value.map(String).join("、");
  }
  if (kind === "entity") return "已选";
  if (kind === "boolean") return typeof value === "boolean" ? (value ? "是" : "否") : "已设置";
  if (kind === "text" || kind === "date") return String(value);
  return "已设置";
}

function savedSearchConditions(query: Record<string, unknown>, fields: readonly SavedSearchConditionField[]): string[] {
  return fields.flatMap(({ key, label, kind }) => {
    const value = savedSearchConditionValue(query[key], kind);
    return value ? [`${label}=${value}`] : [];
  });
}

function savedEntitySearchConditions(query: EntitySearchQuery): string[] {
  const selectedTypes = query.entity_types?.length ? query.entity_types : query.entity_type ? [query.entity_type] : [];
  const conditions = selectedTypes.length
    ? [
        `实体类型=${selectedTypes
          .map((value) => entityTypeLabels[value])
          .filter(Boolean)
          .join("、")}`,
      ]
    : [];
  return conditions;
}

export function savedSearchSummary(saved: SavedSearch): SavedSearchSummary {
  if (saved.query_type === "chemistry_search") {
    const query = saved.query_json as ChemistrySavedSearchQuery;
    const modeLabels: Record<ChemistrySavedSearchQuery["mode"], string> = {
      exact: "精确匹配",
      substructure: "子结构",
      similarity: "相似结构",
    };
    return {
      query: "结构条件",
      type: "结构检索",
      view: "列表",
      conditions: [
        `模式=${modeLabels[query.mode]}`,
        query.mode === "similarity" ? `相似度阈值=${(query.threshold ?? 0.5).toFixed(2)}` : "",
        `结果上限=${query.limit ?? 20}`,
        "结构原文受控保存",
      ].filter(Boolean),
    };
  }
  if (saved.query_type === "pipeline_search") {
    const query = saved.query_json as PipelineSavedSearchQuery;
    return {
      query: query.q ?? "组合条件",
      type: "药物与管线",
      view: savedSearchView(query),
      conditions: savedSearchConditions(query, savedSearchConditionFields.pipeline_search),
    };
  }
  if (saved.query_type === "clinical_trial_search") {
    const query = saved.query_json as ClinicalTrialSavedSearchQuery;
    return {
      query: query.q ?? "组合条件",
      type: "临床试验",
      view: savedSearchView(query),
      conditions: savedSearchConditions(query, savedSearchConditionFields.clinical_trial_search),
    };
  }
  if (saved.query_type === "patent_search") {
    const query = saved.query_json as PatentSavedSearchQuery;
    return {
      query: query.q ?? "组合条件",
      type: "专利情报",
      view: savedSearchView(query),
      conditions: savedSearchConditions(query, savedSearchConditionFields.patent_search),
    };
  }
  if (saved.query_type === "deal_search") {
    const query = saved.query_json as DealSavedSearchQuery;
    return {
      query: query.q ?? "组合条件",
      type: "交易与公司",
      view: savedSearchView(query),
      conditions: savedSearchConditions(query, savedSearchConditionFields.deal_search),
    };
  }
  if (saved.query_type === "regulatory_search") {
    const query = saved.query_json as RegulatorySavedSearchQuery;
    return {
      query: query.q ?? "组合条件",
      type: "监管与安全",
      view: savedSearchView(query),
      conditions: savedSearchConditions(query, savedSearchConditionFields.regulatory_search),
    };
  }
  if (saved.query_type === "epidemiology_search") {
    const query = saved.query_json as EpidemiologySavedSearchQuery;
    return {
      query: query.q ?? "组合条件",
      type: "流行病学",
      view: savedSearchView(query),
      conditions: savedSearchConditions(query, savedSearchConditionFields.epidemiology_search),
    };
  }
  if (saved.query_type === "news_search") {
    const query = saved.query_json as NewsSavedSearchQuery;
    return {
      query: query.q ?? "组合条件",
      type: "新闻与会议",
      view: savedSearchView(query),
      conditions: savedSearchConditions(query, savedSearchConditionFields.news_search),
    };
  }
  const query = saved.query_json as EntitySearchQuery;
  const selectedTypes = query.entity_types?.length ? query.entity_types : query.entity_type ? [query.entity_type] : [];
  const typeLabel =
    selectedTypes
      .slice()
      .sort((left, right) => entityTypeOrder.indexOf(left) - entityTypeOrder.indexOf(right))
      .map((value) => entityTypeLabels[value])
      .filter(Boolean)
      .join("、") || "全部类型";
  return {
    query: query.q ?? "组合条件",
    type: `基础查询 · ${typeLabel}`,
    view: savedSearchView(query),
    conditions: savedEntitySearchConditions(query),
  };
}
