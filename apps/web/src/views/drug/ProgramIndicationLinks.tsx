import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { sourceRecordRows } from "../../lib/sourceRecordRows";
import type { DrugEntityOpener, DrugProgram } from "./types";

export function ProgramIndicationLinks({
  program,
  onOpenEntity,
}: {
  program: DrugProgram;
  onOpenEntity: DrugEntityOpener;
}) {
  const indications = program.indications?.length
    ? program.indications
    : [
        {
          program_id: program.id,
          phase: program.phase,
          disease_entity_id: program.disease_entity_id,
          disease_name: program.disease_name,
        },
      ];
  return (
    <span className="drug-program-entity-list">
      {sourceRecordRows(indications).map(({ value: indication, key }) => (
        <span key={key}>
          {indication.disease_name && indication.disease_entity_id ? (
            <button
              className="table-link-button"
              type="button"
              onClick={() => {
                if (indication.disease_entity_id) onOpenEntity("disease", indication.disease_entity_id);
              }}
            >
              {indication.disease_name}
            </button>
          ) : (
            (indication.disease_name ?? t("未披露"))
          )}
        </span>
      ))}
    </span>
  );
}
