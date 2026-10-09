import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import type { DrugClinicalTrial, DrugEntityOpener } from "./types";
import { trialRoleLabels } from "./vocabulary";

export function TrialRoleLinks({
  trial,
  roles,
  onOpenEntity,
}: {
  trial: DrugClinicalTrial;
  roles: string[];
  onOpenEntity: DrugEntityOpener;
}) {
  const items = (trial.entity_roles ?? []).filter((item) => roles.includes(item.role));
  if (!items.length) return <span>{t("未披露")}</span>;
  return (
    <span className="drug-clinical-role-links">
      {items.map((item) => (
        <button
          type="button"
          key={`${item.role}-${item.entity_id}`}
          aria-label={t("打开{role}：{name}", {
            role: controlledDrugLabel(item.role, trialRoleLabels),
            name: item.name,
          })}
          onClick={() => onOpenEntity(item.entity_type, item.entity_id)}
        >
          <small>{controlledDrugLabel(item.role, trialRoleLabels)}</small>
          {item.name}
        </button>
      ))}
    </span>
  );
}
