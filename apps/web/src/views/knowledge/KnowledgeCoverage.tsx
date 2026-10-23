import type { UseQueryResult } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { EmptyState, ErrorState, Spinner } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { KnowledgeCoverage as Coverage } from "../../lib/contracts/knowledge";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { knowledgeMessages } from "../../lib/i18n/knowledge";
import { knowledgePredicateLabel } from "./knowledgeReading";

export function KnowledgeCoverage({ query }: { query: UseQueryResult<Coverage, Error> }) {
  const text = useMessages(knowledgeMessages);
  const number = new Intl.NumberFormat(formattingLocale());
  if (query.isPending) return <Spinner label={text("正在计算专题覆盖")} />;
  if (query.error)
    return (
      <ErrorState
        message={query.error instanceof Error ? query.error.message : text("专题覆盖加载失败")}
        retry={() => void query.refetch()}
      />
    );
  if (!query.data) return null;
  const coverage = query.data;
  const metrics = [
    ["专题要点", coverage.fact_count],
    ["来源记录", coverage.source_count],
    ["关联实体", coverage.linked_entity_count],
    ["缺少引用", coverage.uncited_fact_count],
  ] as const;
  return (
    <>
      <section className="knowledge-coverage-metrics" aria-label={text("专题覆盖摘要")}>
        {metrics.map(([label, value]) => (
          <div key={label}>
            <strong>{number.format(value)}</strong>
            <span>{text(label)}</span>
          </div>
        ))}
      </section>
      <section className="knowledge-predicate-coverage">
        <header>
          <div>
            <ShieldCheck size={17} />
            <h3>{text("覆盖范围")}</h3>
          </div>
          <span>v{coverage.version_number}</span>
        </header>
        {coverage.predicates.length ? (
          <ScrollableTableRegion ariaLabel={text("知识事实覆盖范围")}>
            <table aria-label={text("知识事实覆盖范围")}>
              <thead>
                <tr>
                  <th>{text("关系类型")}</th>
                  <th>{text("事实数")}</th>
                  <th>{text("已引用")}</th>
                </tr>
              </thead>
              <tbody>
                {coverage.predicates.map((item) => (
                  <tr key={item.predicate}>
                    <td title={item.predicate}>{knowledgePredicateLabel(item.predicate)}</td>
                    <td>{number.format(item.fact_count)}</td>
                    <td>{number.format(item.cited_fact_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title={text("当前版本尚无专题要点")} />
        )}
      </section>
    </>
  );
}
