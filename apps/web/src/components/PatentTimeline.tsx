import { FileKey2, History } from "lucide-react";
import type { PatentFamilyRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { dossierRecordText as t } from "../lib/i18n/dossierRecords";
import { sourceRecordRows } from "../lib/sourceRecordRows";
import { formatDate } from "./common";

export function PatentTimeline({ patent }: { patent: PatentFamilyRead }) {
  useLocale();
  const legalEvents = patent.legal_events ?? [];
  const claims = patent.independent_claims ?? [];
  if (!legalEvents.length && !claims.length) return <span className="muted-value">--</span>;

  return (
    <details className="patent-timeline">
      <summary>
        {t("{events} 个事件 · {claims} 项独立权利要求", { events: legalEvents.length, claims: claims.length })}
      </summary>
      {legalEvents.length ? (
        <section>
          <h4>
            <History size={14} />
            {t("法律事件")}
          </h4>
          <ol>
            {sourceRecordRows(legalEvents).map(({ value: event, key }) => (
              <li key={key}>
                <time>{formatDate(event.occurred_at)}</time>
                <span>
                  <strong>{event.event_type}</strong>
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
            <FileKey2 size={14} />
            {t("独立权利要求摘要")}
          </h4>
          <ol>
            {sourceRecordRows(claims).map(({ value: claim, key }) => (
              <li key={key}>
                <span>
                  <strong>{t("权利要求 {number}", { number: claim.claim_number })}</strong> · {claim.claim_type}
                </span>
                <small>{claim.summary}</small>
                {claim.scope ? <small>{t("范围：{scope}", { scope: claim.scope })}</small> : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </details>
  );
}
