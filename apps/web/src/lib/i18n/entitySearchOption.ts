import { createTranslator } from "./translator";
export const entitySearchOptionMessages = {
  英文名: "English name",
  创新类型: "Innovation type",
  药物类型: "Drug modality",
  药品类别: "Drug category",
  机构类型: "Organization type",
  "国家/地区": "Country / region",
  精确匹配: "Exact match",
  部分匹配: "Partial match",
  相关结果: "Related result",
  关联命中: "Relationship match",
  名称: "Name",
  别名: "Alias",
  数据库编号: "Database identifier",
  简介: "Summary",
  相关内容: "Related content",
  已验证关联: "Verified relationship",
  "：{value}": ": {value}",
  "{source}{relation}{value}": "{source} · {relation}{value}",
  "别名：{aliases}": "Aliases: {aliases}",
} as const;
export const entitySearchOptionText = createTranslator(entitySearchOptionMessages);
