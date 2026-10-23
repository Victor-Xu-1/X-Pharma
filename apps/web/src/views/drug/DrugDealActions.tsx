import { ExternalLink } from "lucide-react";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import type { DrugDeal } from "./types";

export function DrugDealActions({
  deal,
  onOpen,
  onOpenDeal,
}: {
  deal: DrugDeal;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenDeal: (dealId: string) => void;
}) {
  return (
    <div className="row-actions">
      <button
        className="icon-button"
        type="button"
        title={t("打开交易详情")}
        aria-label={t("打开交易详情：{name}", { name: deal.name })}
        onClick={() => onOpenDeal(deal.id)}
      >
        <ExternalLink size={16} />
      </button>
      <ProvenanceButton selection={{ resourceType: "deal", resourceId: deal.id, label: deal.name }} onOpen={onOpen} />
    </div>
  );
}
