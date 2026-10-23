import { dossierRecordText } from "./dossierRecords";
import { getLocale, type Locale } from "./locale";

/** Only entity_dossier.py's application-owned coverage statements are localized. */
export function dossierCoverageNoteText(note: string, locale: Locale = getLocale()): string {
  if (
    note === "当前可查看范围和数据更新时间内暂无记录" ||
    note === "实体级证据通过证据检索和记录来源接口按许可读取" ||
    note === "已返回当前匹配记录"
  ) {
    return dossierRecordText(note, {}, locale);
  }
  const partial = /^返回前 (\d+) 条，完整结果请使用对应分页接口$/u.exec(note);
  if (partial) {
    return dossierRecordText("返回前 {count} 条，完整结果请使用对应分页接口", { count: partial[1] }, locale);
  }
  // Unknown and source-owned notes retain their exact content; never translate scientific prose.
  return note;
}
