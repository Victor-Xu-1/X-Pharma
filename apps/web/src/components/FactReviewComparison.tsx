import type { UseQueryResult } from "@tanstack/react-query";
import "../styles/fact-review-comparison.css";

import type { StagedFact } from "../lib/contracts/governance";
import type { GovernanceFactComparisonRead, GovernanceFactOriginRead } from "../lib/generated";
import { governanceLabel, payloadDifferences, reviewValue } from "../lib/governancePresentation";
import { useLocale } from "../lib/i18n";
import { governanceEvidenceText as t } from "../lib/i18n/governanceEvidence";
import { ErrorState, formatDate, Spinner, StatusBadge } from "./common";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

function Origin({ origin }: { origin: GovernanceFactOriginRead | null }) {
  useLocale();
  if (!origin) return <p>{t("来源运行记录不可用，不能确认解析方式。")}</p>;
  return (
    <dl className="review-source">
      <div>
        <dt>{t("解析方式")}</dt>
        <dd>{t(origin.model_provider === "deterministic-adapter" ? "确定性适配器（非模型推断）" : "模型提取")}</dd>
      </div>
      <div>
        <dt>{t("解析器 / 模型")}</dt>
        <dd>{origin.model_name}</dd>
      </div>
      <div>
        <dt>{t("来源")}</dt>
        <dd>{origin.source_name}</dd>
      </div>
      <div>
        <dt>{t("来源文件 · 版本 {version}", { version: origin.source_version_number })}</dt>
        <dd>{origin.source_file_name}</dd>
      </div>
      <div>
        <dt>{t("采集时间")}</dt>
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
  useLocale();
  const differences = payloadDifferences(before, after);
  if (!differences.length) return <p>{t("业务字段一致；引证元数据另行保留。")}</p>;
  return (
    <ScrollableTableRegion
      ariaLabel={t("{before}与{after}字段对照", { before: beforeTitle, after: afterTitle })}
      className="review-field-differences"
    >
      <table>
        <thead>
          <tr>
            <th scope="col">{t("字段")}</th>
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
    </ScrollableTableRegion>
  );
}

export function FactReviewComparison({
  fact,
  comparison,
  onRetry,
}: {
  fact: StagedFact;
  comparison: Pick<UseQueryResult<GovernanceFactComparisonRead>, "isPending" | "data" | "error">;
  onRetry: () => void;
}) {
  useLocale();
  if (comparison.isPending) return <Spinner label={t("正在读取来源与冲突对照")} />;
  if (comparison.error)
    return (
      <ErrorState
        message={comparison.error instanceof Error ? comparison.error.message : t("来源与冲突对照读取失败")}
        retry={onRetry}
      />
    );
  const data = comparison.data;
  if (!data || data.fact.id !== fact.id || data.fact.status !== fact.status)
    return <ErrorState message={t("对照记录与当前审核事实不匹配")} retry={onRetry} />;
  return (
    <>
      <section>
        <h3>{t("来源与解析方式")}</h3>
        <Origin origin={data.origin} />
        <p className="field-help">{t("解析评分不代表事实正确性。存在冲突时，必须核对来源并填写审核依据。")}</p>
      </section>
      <section>
        <h3>{t("规范化差异")}</h3>
        {fact.normalization_version ? <p className="normalization-version">{fact.normalization_version}</p> : null}
        <FieldDifferences
          before={fact.raw_payload}
          after={fact.payload}
          beforeTitle={t("来源解析值")}
          afterTitle={t("平台规范化结果")}
        />
      </section>
      {data.conflict_total > 0 ? (
        <section>
          <h3>
            {data.conflict_total === 1
              ? t("历史事实对照 · 1 条")
              : t("历史事实对照 · {count} 条", { count: data.conflict_total })}
          </h3>
          {data.conflicts.map((item) => (
            <details key={item.fact.id} open={data.conflicts.length === 1}>
              <summary>
                {formatDate(item.fact.created_at, true)} <StatusBadge value={item.fact.status} />
              </summary>
              <Origin origin={item.origin} />
              <FieldDifferences
                before={item.fact.payload}
                after={fact.payload}
                beforeTitle={t("历史记录")}
                afterTitle={t("本次候选")}
              />
              <blockquote>{item.fact.source_quote}</blockquote>
              <p>{t("来源定位：{locator}", { locator: item.fact.source_locator ?? t("未提供") })}</p>
            </details>
          ))}
          {data.unavailable_conflicts ? (
            <p role="status">
              {t("本次有 {count} 条历史记录不可用；不会跨组织读取。", { count: data.unavailable_conflicts })}
            </p>
          ) : null}
          {data.truncated ? <p>{t("本次展示至多 20 条记录；其余历史未删除。")}</p> : null}
        </section>
      ) : null}
      <details>
        <summary>{t("技术详情与完整原始记录")}</summary>
        <h4>
          {t(
            data.origin?.model_provider === "deterministic-adapter"
              ? "来源解析值（确定性适配器）"
              : data.origin
                ? "模型提取值"
                : "来源解析值（方式未确认）",
          )}
        </h4>
        <pre className="json-preview">{JSON.stringify(fact.raw_payload, null, 2)}</pre>
        <h4>{t("平台规范化结果")}</h4>
        <pre className="json-preview">{JSON.stringify(fact.payload, null, 2)}</pre>
        <p>{t("来源摘要：{hash}", { hash: data.origin?.source_content_sha256 ?? t("未提供") })}</p>
      </details>
    </>
  );
}
