import { createTranslator } from "./translator";

export const evidenceMessages = {
  研究问题或查证内容: "Research question or evidence query",
  "输入靶点、活性值、专利号、试验号或项目事实":
    "Enter a target, activity value, patent, trial identifier or project fact",
  证据域: "Evidence domains",
  正在加载已授权证据域: "Loading authorized evidence domains",
  "证据域加载失败，重试": "Evidence domains could not be loaded. Retry",
  暂无可用证据域: "No evidence domains are available",
  不选择时检索全部已授权证据域: "With none selected, search all authorized evidence domains",
  查证原文: "Search source evidence",
  正在检索原始证据: "Searching source evidence",
  证据检索参数缺失: "Evidence query parameters are missing",
  个引用片段: "citation excerpts",
  该引用已不在当前检索结果中: "This citation is no longer in the current results",
  清除失效定位: "Clear stale citation location",
  当前引用定位: "Current citation location",
  "引用 {number} · {locator}": "Citation {number} · {locator}",
  来源: "Source",
  已授权资料: "Authorized material",
  来源说明: "Source attribution",
  原始资料: "Original material",
  访问原始来源: "Open original source",
  已定位此引用: "Current citation",
  "定位引用 {number}": "Locate citation {number}",
  未找到匹配证据: "No matching evidence found",
  等待查证: "Awaiting evidence search",
  "检索结果将保留原文片段、文档来源和定位信息":
    "Results retain source excerpts, document provenance and citation locations",
  收起完整引用: "Collapse full citation",
  展开完整引用: "Expand full citation",
  页: "Page",
  幻灯片: "Slide",
  工作表: "Sheet",
  行: "Row",
  文本行: "Line",
  段落: "Paragraph",
  章节: "Section",
  "字符 {start}-{end}": "Characters {start}-{end}",
  来源未提供页码或段落定位: "The source did not provide a page or paragraph location",
} as const;

export const evidenceText = createTranslator(evidenceMessages);
