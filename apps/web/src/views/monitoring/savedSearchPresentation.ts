import type { SavedSearch } from "../../lib/contracts/monitoring";
import { entityLabels } from "../../lib/entityPresentation";
import type { ChemistrySavedSearchQuery, EntitySearchQuery, EntityType } from "../../lib/generated";
import { formattingLocale } from "../../lib/i18n";
import { savedSearchText as text } from "../../lib/i18n/savedSearch";
import { savedSearchConditionFields } from "./savedSearchConditionFields";
import { savedSearchConditionValue } from "./savedSearchConditionValue";

// Retain the original saved-query display order; labels have one shared owner.
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
const domainLabels = {
  pipeline_search: "药物与管线",
  clinical_trial_search: "临床试验",
  patent_search: "专利情报",
  deal_search: "交易与公司",
  regulatory_search: "监管与安全",
  epidemiology_search: "流行病学",
  news_search: "新闻与会议",
} as const;
type SavedSearchSummary = { query: string; type: string; view: string; conditions: string[] };

function savedSearchView(query: Record<string, unknown>): string {
  if (query.display_mode === "timeline") return text("时间线");
  if (query.display_mode === "landscape") return query.analysis_view === "table" ? text("统计表") : text("统计图");
  return text("列表");
}
function typeNames(types: readonly EntityType[]): string {
  const labels = entityLabels();
  return types
    .map((value) => (Object.hasOwn(labels, value) ? labels[value] : value))
    .join(formattingLocale() === "en-US" ? ", " : "、");
}

function conditions(query: Record<string, unknown>, kind: string): string[] {
  return savedSearchConditionFields[kind].flatMap(({ key, label, kind: fieldKind }) => {
    const value = savedSearchConditionValue(query[key], key, kind, fieldKind);
    return value !== null ? [`${text(label)}=${value}`] : [];
  });
}

/** A presentation projection only. Replay always uses the original authorized query. */
export function savedSearchSummary(saved: SavedSearch): SavedSearchSummary {
  if (saved.query_type === "chemistry_search") {
    const query = saved.query_json as ChemistrySavedSearchQuery;
    const modeLabels = { exact: "精确匹配", substructure: "子结构", similarity: "相似结构" } as const;
    return {
      query: text("结构条件"),
      type: text("结构检索"),
      view: text("列表"),
      conditions: [
        `${text("模式")}=${text(modeLabels[query.mode])}`,
        query.mode === "similarity" ? `${text("相似度阈值")}=${(query.threshold ?? 0.5).toFixed(2)}` : "",
        `${text("结果上限")}=${query.limit ?? 20}`,
        text("结构原文受控保存"),
      ].filter(Boolean),
    };
  }
  const query = saved.query_json as Record<string, unknown>;
  const keyword = typeof query.q === "string" && query.q.trim() ? query.q : text("组合条件");
  if (Object.hasOwn(domainLabels, saved.query_type)) {
    const kind = saved.query_type as keyof typeof domainLabels;
    return {
      query: keyword,
      type: text(domainLabels[kind]),
      view: savedSearchView(query),
      conditions: conditions(query, kind),
    };
  }
  const entityQuery = saved.query_json as EntitySearchQuery;
  const selectedTypes = entityQuery.entity_types?.length
    ? entityQuery.entity_types
    : entityQuery.entity_type
      ? [entityQuery.entity_type]
      : [];
  const typeLabel =
    typeNames(
      selectedTypes.slice().sort((left, right) => entityTypeOrder.indexOf(left) - entityTypeOrder.indexOf(right)),
    ) || text("全部类型");
  return {
    query: keyword,
    type: text("基础查询 · {types}", { types: typeLabel }),
    view: savedSearchView(query),
    conditions: [
      ...(selectedTypes.length ? [`${text("实体类型")}=${typeNames(selectedTypes)}`] : []),
      ...conditions(query, "entity_search"),
    ],
  };
}
