import { createTranslator } from "./translator";

export const domainLandscapeMessages = {
  正在绘制分布: "Drawing distribution",
  "{title}{unit}分布": "{title} {unit} distribution",
  "{title}统计表滚动区域": "{title} statistics scroll region",
  "{title}统计表": "{title} statistics",
  排名: "Rank",
  分类: "Category",
  占比: "Share",
  操作: "Actions",
  筛选: "Filter",
  "当前查询没有可统计的记录。": "No records to summarize for this query.",
  完整命中集: "Complete result set",
  "统计与当前筛选、租户授权和数据时点一致，不受当前分页影响。":
    "Statistics follow the applied filters, organization access and data timestamp, independent of pagination.",
  统计展示方式: "Statistics presentation",
  图示: "Chart",
  列表: "Table",
  笔交易: "deals",
} as const;

export const domainLandscapeText = createTranslator(domainLandscapeMessages);
