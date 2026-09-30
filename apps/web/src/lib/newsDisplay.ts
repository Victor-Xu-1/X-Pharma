import type { EntityType } from "./generated";

export const newsEntityTypes = [
  "drug",
  "target",
  "disease",
  "organization",
  "technology",
] as const satisfies readonly EntityType[];

export const newsEventTypeLabels: Record<string, string> = {
  news: "新闻",
  press_release: "新闻稿",
  corporate_announcement: "公司公告",
  publication: "论文发表",
  conference_abstract: "会议摘要",
  poster: "会议海报",
  presentation: "会议演示",
  other: "其他",
};

export const newsLanguageLabels: Record<string, string> = {
  zh: "中文",
  en: "英文",
};
