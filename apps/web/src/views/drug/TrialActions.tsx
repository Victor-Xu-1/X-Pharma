import { ExternalLink } from "lucide-react";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import type { DrugClinicalTrial } from "./types";

export function TrialActions({
  trial,
  onOpen,
  onOpenTrial,
}: {
  trial: DrugClinicalTrial;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenTrial: (trialId: string) => void;
}) {
  return (
    <div className="row-actions">
      <button
        className="icon-button"
        type="button"
        title={t("打开临床试验详情")}
        aria-label={t("打开临床试验详情：{registry}", { registry: trial.registry_id })}
        onClick={() => onOpenTrial(trial.id)}
      >
        <ExternalLink size={16} />
      </button>
      <ProvenanceButton
        selection={{ resourceType: "clinical_trial", resourceId: trial.id, label: trial.registry_id }}
        onOpen={onOpen}
      />
    </div>
  );
}
