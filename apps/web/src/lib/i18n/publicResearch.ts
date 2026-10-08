import { createTranslator } from "./translator";

export const publicResearchMessages = {
  综合调研: "Overview research",
  药物: "Drugs",
  靶点: "Targets",
  临床试验: "Clinical trials",
  试验申办方: "Trial sponsors",
  研究条件: "Study conditions",
  "关键词专利（历史著录）": "Keyword patents (historical metadata)",
  "化合物专利引用（药物名/CID）": "Compound patent references (drug name / CID)",
  文献: "Literature",
  "公司公告／交易线索": "Company disclosures / deal leads",
  公开检索尚未执行: "Public search has not been executed.",
  公开来源调研: "Public-source research",
  "补充本地覆盖 · 按需联网查询": "Supplement local coverage · Search online on demand",
  查看本地数据覆盖: "View local data coverage",
  正在读取本地覆盖: "Loading local coverage",
  本地覆盖读取失败: "Could not load local coverage.",
  未登记: "Not registered",
  "已登记公开来源：{sources}": "Registered public sources: {sources}",
  "、": ", ",
  刷新本地覆盖: "Refresh local coverage",
  "仅点击“查询公开来源”后才发送下方关键词。不要输入患者、未公开项目或其他保密信息；联网结果与本地已核验数据分开。":
    "Keywords below are sent only when you choose Search public sources. Do not enter patient information, unpublished projects or other confidential data. Online results are separate from verified local data.",
  公开来源检索: "Public-source search",
  公开关键词: "Public keywords",
  "英文靶点、药物、公司或研究主题": "English target, drug, company or research topic",
  调研范围: "Research scope",
  查询公开来源: "Search public sources",
  正在查询公开来源: "Searching public sources",
  取消等待: "Cancel waiting",
  "已取消本次等待；来源请求将在有界时限内结束，未写入本地事实。":
    "Waiting cancelled. Source requests will end within their bounded deadline; no local facts were written.",
  "公开查询失败，请明确重试": "Public search failed. Retry explicitly to send another request.",
  公开调研结果: "Public research results",
  可读取: "Available",
  当前范围未命中: "No matches in this scope",
  暂不可用: "Temporarily unavailable",
  "已查询：{query} · {observed} · 公开元数据，未自动入库或核验为事实。":
    "Query: {query} · {observed} · Public metadata only; not automatically stored or verified as facts.",
  "来源命中 {count} 条": "{count} source matches",
  "来源日期：{date} · ": "Source date: {date} · ",
  "来源日期未提供 · ": "Source date not provided · ",
  到来源继续检索: "Continue searching at the source",
} as const;

export const publicResearchText = createTranslator(publicResearchMessages);
