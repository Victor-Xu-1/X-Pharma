import { ArrowUpRight, Search } from "lucide-react";
import { useLocale } from "../lib/i18n";
import { queryText as t } from "../lib/i18n/query";
import "./ResearchStart.css";

/** Example queries use the normal search path; they are not curated scientific claims. */
export function ResearchStart({ onSearch }: { onSearch: (query: string) => void }) {
  useLocale();
  return (
    <section className="research-start" aria-label={t("开始情报研究")}>
      <div className="research-start-icon">
        <Search size={24} strokeWidth={1.5} aria-hidden="true" />
      </div>
      <h2>{t("输入检索条件")}</h2>
      <p>{t("从一个药物、靶点或外部标识开始，沿着关联与来源深入研究。")}</p>
      <fieldset className="research-start-examples">
        <legend className="sr-only">{t("示例检索")}</legend>
        <span>{t("试试检索")}</span>
        {["EGFR", "HER2", "OSIMERTINIB"].map((query) => (
          <button
            key={query}
            type="button"
            onClick={() => onSearch(query)}
            aria-label={t("检索示例 {query}", { query })}
          >
            {query}
            <ArrowUpRight size={14} aria-hidden="true" />
          </button>
        ))}
      </fieldset>
      <small>{t("仅检索当前组织获授权的已发布数据；来源覆盖不等于完整研究结论。")}</small>
    </section>
  );
}
