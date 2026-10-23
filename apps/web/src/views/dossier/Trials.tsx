import { CalendarDays } from "lucide-react";
import { EmptyState, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { localizedTrialPhase } from "../../lib/i18n/trialVocabulary";
import type { DossierSectionProps } from "./types";

export function Trials({
  data,
  onOpen,
  onOpenTrial,
}: DossierSectionProps & { onOpenTrial: (trialId: string) => void }) {
  useLocale();
  if (!data.clinical_trials.length) return <EmptyState title={t("暂无关联临床试验")} />;
  return (
    <div className="entity-record-list">
      {data.clinical_trials.map((item) => (
        <article key={item.id}>
          <CalendarDays size={18} />
          <div>
            <span>
              {item.registry_id} · {item.phases.map(localizedTrialPhase).join(" / ") || t("阶段未记录")}
            </span>
            <h3>
              <button className="table-link-button" type="button" onClick={() => onOpenTrial(item.id)}>
                {item.official_title}
              </button>
            </h3>
            <p>{item.conditions.join(t("、")) || t("适应症未记录")}</p>
          </div>
          <StatusBadge value={item.overall_status ?? "unknown"} />
          <ProvenanceButton
            selection={{ resourceType: "clinical_trial", resourceId: item.id, label: item.registry_id }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}
