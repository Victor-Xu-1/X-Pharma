import { GitBranch } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { PatentTimeline } from "../../components/PatentTimeline";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { patentLegalStatusLabels } from "../../lib/contracts/patents";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import type { DossierSectionProps } from "./types";

export function Patents({
  data,
  onOpen,
  onOpenPatent,
}: DossierSectionProps & { onOpenPatent: (patentId: string) => void }) {
  useLocale();
  if (!data.patents.length) return <EmptyState title={t("暂无关联专利")} />;
  return (
    <div className="entity-record-list entity-patent-list">
      {data.patents.map((item) => (
        <article key={item.id}>
          <GitBranch size={18} />
          <div>
            <span>{item.family_identifier}</span>
            <h3>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenPatent(item.id)}
                aria-label={t("打开专利族详情：{id}", { id: item.family_identifier })}
              >
                {item.title}
              </button>
            </h3>
            <p>
              {t("{applicants} · 优先权 {date}", {
                applicants: item.applicants.join("、") || t("申请人未记录"),
                date: formatDate(item.priority_date),
              })}
            </p>
          </div>
          <StatusBadge
            value={item.legal_status ?? "unknown"}
            label={controlledDrugLabel(item.legal_status, patentLegalStatusLabels)}
          />
          <PatentTimeline patent={item} />
          <ProvenanceButton
            selection={{ resourceType: "patent_family", resourceId: item.id, label: item.family_identifier }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}
