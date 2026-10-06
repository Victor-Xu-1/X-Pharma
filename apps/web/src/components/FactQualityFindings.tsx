import { governanceLabel, reviewValue } from "../lib/governancePresentation";
import { StatusBadge } from "./common";

const descriptions: Record<string, string> = {
  conflicting_fact: "历史事实与本次候选包含不同字段值",
  structure_authority_mismatch: "来源结构字段与平台 RDKit 派生结果不一致",
  quote_not_found_in_segment: "引文未在本次输入片段中找到",
  stale_official_source_version: "该来源记录已有更新版本，本次旧版本不能覆盖",
  policy_review: "按当前字段类型或提取策略，需要人工审核",
  canonical_structure_conflict: "结构已经关联到另一规范对象，需要核对身份",
};

export function FactQualityFindings({ findings }: { findings: Record<string, unknown>[] }) {
  const entries = new Map(findings.map((finding) => [JSON.stringify(finding), finding] as const));
  return (
    <section>
      <h3>质量发现</h3>
      <ul>
        {[...entries].map(([key, finding]) => {
          const code = typeof finding.code === "string" ? finding.code : "unknown";
          const message = descriptions[code] ?? (typeof finding.message === "string" ? finding.message : code);
          return (
            <li key={key}>
              <p>
                {message} {typeof finding.severity === "string" ? <StatusBadge value={finding.severity} /> : null}
              </p>
              {typeof finding.field === "string" ? <p>字段：{governanceLabel(finding.field)}</p> : null}
              {Object.hasOwn(finding, "model_value") ? <p>来源值：{reviewValue(finding.model_value)}</p> : null}
              {Object.hasOwn(finding, "derived_value") ? <p>平台派生值：{reviewValue(finding.derived_value)}</p> : null}
            </li>
          );
        })}
      </ul>
      <details>
        <summary>完整质量记录</summary>
        <pre className="json-preview compact">{JSON.stringify(findings, null, 2)}</pre>
      </details>
    </section>
  );
}
