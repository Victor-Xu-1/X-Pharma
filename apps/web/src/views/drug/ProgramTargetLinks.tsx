import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import type { DrugEntityOpener, DrugProgram } from "./types";

export function ProgramTargetLinks({
  program,
  onOpenEntity,
}: {
  program: DrugProgram;
  onOpenEntity: DrugEntityOpener;
}) {
  const targets = program.targets?.length
    ? program.targets
    : program.target_entity_id && program.target_name
      ? [{ entity_id: program.target_entity_id, name: program.target_name, role: "primary", position: 0 }]
      : [];
  if (!targets.length) return <span>{t("未披露")}</span>;
  return (
    <span className="drug-program-targets">
      {targets.map((target) => (
        <button
          className="table-link-button"
          type="button"
          key={`${program.id}-${target.entity_id}-${target.role}`}
          onClick={() => onOpenEntity("target", target.entity_id)}
        >
          {target.name}
        </button>
      ))}
    </span>
  );
}
