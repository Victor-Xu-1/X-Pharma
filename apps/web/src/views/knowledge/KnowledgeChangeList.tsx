import { FileText } from "lucide-react";
import type { KnowledgeVersionDiff } from "../../lib/contracts/knowledge";
import { KnowledgeFactValue } from "./KnowledgeFactValue";
import { knowledgePredicateLabel, recordValue } from "./knowledgeReading";

export function KnowledgeChangeList({ diff, kind }: { diff: KnowledgeVersionDiff; kind: "added" | "removed" }) {
  const facts = kind === "added" ? diff.added_facts : diff.removed_facts;
  const sources = kind === "added" ? diff.added_sources : diff.removed_sources;
  const title = kind === "added" ? "新增" : "移除";
  if (!facts.length && !sources.length) return null;
  return (
    <section className={`knowledge-change-group ${kind}`} aria-label={`${title}要点`}>
      <h4>{title}</h4>
      {facts.length ? (
        <div className="knowledge-change-list">
          {facts.map((fact) => {
            const locator = fact.source_locator ?? recordValue(recordValue(fact.value)?.citation)?.locator;
            return (
              <article key={fact.change_key}>
                <div>
                  <strong title={fact.predicate}>{knowledgePredicateLabel(fact.predicate)}</strong>
                  <KnowledgeFactValue value={fact.value} objectName={fact.object_entity_name} />
                </div>
                <small>
                  {fact.source_title || (typeof locator === "string" ? "记录定位" : "未附带来源标注")}
                  {typeof locator === "string" ? ` · ${locator}` : ""}
                </small>
              </article>
            );
          })}
        </div>
      ) : null}
      {sources.length ? (
        <div className="knowledge-source-changes">
          {sources.map((source) => (
            <p key={`${source.title}:${source.locator ?? ""}`}>
              <FileText size={14} aria-hidden="true" />
              <span>{source.title}</span>
              {source.locator ? <small>{source.locator}</small> : null}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}
