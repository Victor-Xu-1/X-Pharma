import { CalendarDays, FileText, MapPin, Users } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import type { ClinicalTrialDetailRead } from "../../lib/generated";
import { formattingLocale } from "../../lib/i18n";
import { clinicalText as t } from "../../lib/i18n/clinical";
import { localizedTrialStatus } from "../../lib/i18n/trialVocabulary";
import { sourceRecordRows } from "../../lib/sourceRecordRows";
export function TrialTimeline({ data }: { data: ClinicalTrialDetailRead }) {
  return (
    <div className="trial-detail-sections">
      <section>
        <h3>{t("状态时间线")}</h3>
        {data.status_history.length ? (
          <ol className="trial-status-timeline">
            {sourceRecordRows([...data.status_history].reverse()).map(({ value: event, key }) => (
              <li key={key}>
                <CalendarDays size={17} />
                <div>
                  <strong>{localizedTrialStatus(event.status)}</strong>
                  <span>{formatDate(event.effective_at, true)}</span>
                  {event.reason ? <p>{event.reason}</p> : null}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState title={t("暂无历史状态记录")} />
        )}
      </section>
      <section>
        <h3>{t("研究中心")}</h3>
        {data.locations.length ? (
          <div className="trial-location-list">
            {sourceRecordRows(data.locations).map(({ value: location, key }) => (
              <div key={key}>
                <MapPin size={17} />
                <div>
                  <strong>{location.facility ?? location.city ?? location.country}</strong>
                  <span>{[location.city, location.state, location.country].filter(Boolean).join(" · ")}</span>
                </div>
                {location.status ? (
                  <StatusBadge value={location.status} label={localizedTrialStatus(location.status)} />
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title={t("暂无研究中心记录")} />
        )}
      </section>
      <section className="trial-source-summary">
        <FileText size={18} />
        <div>
          <strong>{data.source_document_id ? t("来源记录已收录") : t("来源记录待补充")}</strong>
          <span>{t("最近更新 {date}", { date: formatDate(data.last_update_posted, true) })}</span>
        </div>
        <Users size={18} />
        <span>{t("{count} 人", { count: data.enrollment?.toLocaleString(formattingLocale()) ?? "--" })}</span>
      </section>
    </div>
  );
}
