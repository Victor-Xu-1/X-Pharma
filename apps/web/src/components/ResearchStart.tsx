import { ArrowUpRight, Search } from "lucide-react";
import "./ResearchStart.css";

/** Example queries use the normal search path; they are not curated scientific claims. */
export function ResearchStart({ onSearch }: { onSearch: (query: string) => void }) {
  return (
    <section className="research-start" aria-label="开始情报研究">
      <div className="research-start-icon">
        <Search size={24} strokeWidth={1.5} aria-hidden="true" />
      </div>
      <h2>输入检索条件</h2>
      <p>从一个药物、靶点或外部标识开始，沿着关联与来源深入研究。</p>
      <fieldset className="research-start-examples">
        <legend className="sr-only">示例检索</legend>
        <span>试试检索</span>
        {["EGFR", "HER2", "OSIMERTINIB"].map((query) => (
          <button key={query} type="button" onClick={() => onSearch(query)} aria-label={`检索示例 ${query}`}>
            {query}
            <ArrowUpRight size={14} aria-hidden="true" />
          </button>
        ))}
      </fieldset>
      <small>仅检索当前组织获授权的已发布数据；来源覆盖不等于完整研究结论。</small>
    </section>
  );
}
