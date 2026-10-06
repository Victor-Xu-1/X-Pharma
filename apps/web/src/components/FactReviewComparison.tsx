import { useQuery } from "@tanstack/react-query";
import "../styles/fact-review-comparison.css";

import { governanceKeys, loadFactComparison, type StagedFact } from "../lib/contracts/governance";
import type { GovernanceFactOriginRead } from "../lib/generated";
import { governanceLabel, payloadDifferences, reviewValue } from "../lib/governancePresentation";
import { ErrorState, formatDate, Spinner, StatusBadge } from "./common";

function Origin({ origin }: { origin: GovernanceFactOriginRead | null }) {
  if (!origin) return <p>来源运行记录不可用，不能确认解析方式。</p>;
  return (
    <dl className="review-source">
      <div>
        <dt>解析方式</dt>
        <dd>{origin.model_provider === "deterministic-adapter" ? "确定性适配器（非模型推断）" : "模型提取"}</dd>
      </div>
      <div>
        <dt>解析器 / 模型</dt>
        <dd>{origin.model_name}</dd>
      </div>
      <div>
        <dt>来源</dt>
        <dd>
          {origin.source_name} · {origin.source_file_name} · 版本 {origin.source_version_number}
        </dd>
      </div>
      <div>
        <dt>采集时间</dt>
        <dd>{formatDate(origin.collected_at, true)}</dd>
      </div>
    </dl>
  );
}

export function FieldDifferences({
  before,
  after,
  beforeTitle,
  afterTitle,
}: {
  before: unknown;
  after: unknown;
  beforeTitle: string;
  afterTitle: string;
}) {
  const differences = payloadDifferences(before, after);
  if (!differences.length) return <p>业务字段一致；引证元数据另行保留。</p>;
  return (
    <div className="review-field-differences">
      <table>
        <thead>
          <tr>
            <th scope="col">字段</th>
            <th scope="col">{beforeTitle}</th>
            <th scope="col">{afterTitle}</th>
          </tr>
        </thead>
        <tbody>
          {differences.map((item) => (
            <tr key={item.path}>
              <th scope="row">{governanceLabel(item.path)}</th>
              <td>{reviewValue(item.before)}</td>
              <td>{reviewValue(item.after)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FactReviewComparison({ fact }: { fact: StagedFact }) {
  const comparison = useQuery({
    queryKey: governanceKeys.factComparison(fact.id),
    queryFn: ({ signal }) => loadFactComparison(fact.id, signal),
  });
  if (comparison.isPending) return <Spinner label="正在读取来源与冲突对照" />;
  if (comparison.error) return <ErrorState message="来源与冲突对照读取失败" retry={() => void comparison.refetch()} />;
  const data = comparison.data;
  return (
    <>
      <section>
        <h3>来源与解析方式</h3>
        <Origin origin={data.origin} />
        <p>解析评分不代表事实正确性。存在冲突时，必须核对来源并填写审核依据。</p>
      </section>
      <section>
        <h3>规范化差异</h3>
        {fact.normalization_version ? <p className="normalization-version">{fact.normalization_version}</p> : null}
        <FieldDifferences
          before={fact.raw_payload}
          after={fact.payload}
          beforeTitle="来源解析值"
          afterTitle="平台规范化结果"
        />
      </section>
      {data.conflict_total > 0 ? (
        <section>
          <h3>历史事实对照 · {data.conflict_total} 条</h3>
          {data.conflicts.map((item) => (
            <details key={item.fact.id} open={data.conflicts.length === 1}>
              <summary>
                {formatDate(item.fact.created_at, true)} <StatusBadge value={item.fact.status} />
              </summary>
              <Origin origin={item.origin} />
              <FieldDifferences
                before={item.fact.payload}
                after={fact.payload}
                beforeTitle="历史记录"
                afterTitle="本次候选"
              />
              <blockquote>{item.fact.source_quote}</blockquote>
              <p>来源定位：{item.fact.source_locator ?? "未提供"}</p>
            </details>
          ))}
          {data.unavailable_conflicts ? (
            <p role="status">本次有 {data.unavailable_conflicts} 条历史记录不可用；不会跨组织读取。</p>
          ) : null}
          {data.truncated ? <p>本次展示至多 20 条记录；其余历史未删除。</p> : null}
        </section>
      ) : null}
      <details>
        <summary>技术详情与完整原始记录</summary>
        <h4>
          {data.origin?.model_provider === "deterministic-adapter"
            ? "来源解析值（确定性适配器）"
            : data.origin
              ? "模型提取值"
              : "来源解析值（方式未确认）"}
        </h4>
        <pre className="json-preview">{JSON.stringify(fact.raw_payload, null, 2)}</pre>
        <h4>平台规范化结果</h4>
        <pre className="json-preview">{JSON.stringify(fact.payload, null, 2)}</pre>
        <p>来源摘要：{data.origin?.source_content_sha256 ?? "未提供"}</p>
      </details>
    </>
  );
}
