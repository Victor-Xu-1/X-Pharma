import { FileKey2, History } from "lucide-react";

import type { PatentFamilyRead } from "../lib/generated";
import { formatDate } from "./common";

export function PatentTimeline({ patent }: { patent: PatentFamilyRead }) {
  const legalEvents = patent.legal_events ?? [];
  const claims = patent.independent_claims ?? [];
  if (!legalEvents.length && !claims.length) return <span className="muted-value">--</span>;

  return (
    <details className="patent-timeline">
      <summary>
        {legalEvents.length} 个事件 · {claims.length} 项独立权利要求
      </summary>
      {legalEvents.length ? (
        <section>
          <h4>
            <History size={14} /> 法律事件
          </h4>
          <ol>
            {legalEvents.map((event) => (
              <li
                key={`${event.event_type}-${event.occurred_at}-${event.jurisdiction ?? "unknown"}-${event.publication_number ?? "family"}`}
              >
                <time>{formatDate(event.occurred_at)}</time>
                <span>
                  <strong>{event.event_type.replaceAll("_", " ")}</strong>
                  {event.status ? ` · ${event.status}` : ""}
                  {event.jurisdiction ? ` · ${event.jurisdiction}` : ""}
                </span>
                {event.description ? <small>{event.description}</small> : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      {claims.length ? (
        <section>
          <h4>
            <FileKey2 size={14} /> 独立权利要求摘要
          </h4>
          <ol>
            {claims.map((claim) => (
              <li key={`${claim.claim_number}-${claim.claim_type}`}>
                <span>
                  <strong>权利要求 {claim.claim_number}</strong> · {claim.claim_type}
                </span>
                <small>{claim.summary}</small>
                {claim.scope ? <small>范围：{claim.scope}</small> : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </details>
  );
}
