import type { DrugDossier } from "../../lib/contracts/drugDossier";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { programOrganizations } from "./programPresentation";
import type { DrugEntityOpener, EntityLink } from "./types";

export function uniqueProgramEntities(data: DrugDossier, kind: "target" | "disease" | "organization"): EntityLink[] {
  const values: EntityLink[] = [];
  for (const program of data.programs) {
    if (kind === "target") {
      const programTargets = program.targets ?? [];
      const targets = programTargets.length
        ? programTargets.map((target) => ({ id: target.entity_id, name: target.name }))
        : program.target_entity_id && program.target_name
          ? [{ id: program.target_entity_id, name: program.target_name }]
          : [];
      values.push(...targets.map((item) => ({ ...item, kind })));
    } else if (kind === "disease") {
      const indicationCount = values.length;
      for (const indication of program.indications ?? []) {
        if (indication.disease_entity_id && indication.disease_name) {
          values.push({ id: indication.disease_entity_id, name: indication.disease_name, kind });
        }
      }
      if (values.length === indicationCount && program.disease_entity_id && program.disease_name) {
        values.push({ id: program.disease_entity_id, name: program.disease_name, kind });
      }
    } else if (kind === "organization") {
      values.push(
        ...programOrganizations(program).map((organization) => ({
          id: organization.entity_id,
          name: organization.name,
          kind,
        })),
      );
    }
  }
  return Array.from(new Map(values.map((item) => [item.id, item])).values()).sort((left, right) =>
    left.name.localeCompare(right.name),
  );
}

export function renderEntityLinks(items: EntityLink[], onOpenEntity: DrugEntityOpener) {
  if (!items.length) return t("未披露");
  return items.map((item, index) => (
    <span key={item.id}>
      {index > 0 ? t("、") : ""}
      <button className="inline-link-button" type="button" onClick={() => onOpenEntity(item.kind, item.id)}>
        {item.name}
      </button>
    </span>
  ));
}
