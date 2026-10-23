import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import type { DrugProgram } from "./types";
import { geographyLabels } from "./vocabulary";

export function governedDisplay(value: string, labels: Record<string, string>) {
  return controlledDrugLabel(value, labels);
}

export function geographyLabel(value: string | null | undefined): string {
  return controlledDrugLabel(value, geographyLabels);
}

export function listValues(values: string[] | null | undefined, empty = t("未披露")): string {
  if (!values?.length) return empty;
  return Array.from(new Set(values)).join(t("、"));
}

export function listRegions(values: string[] | null | undefined): string {
  return listValues(values?.map((value) => geographyLabel(value)));
}

export function governedValue(value: string | null | undefined, labels: Record<string, string>): string | null {
  return value ? controlledDrugLabel(value, labels) : null;
}

export function programOrganizations(program: DrugProgram): NonNullable<DrugProgram["organizations"]> {
  if (program.organizations?.length) return program.organizations;
  if (!program.organization_entity_id || !program.organization_name) return [];
  return [
    {
      entity_id: program.organization_entity_id,
      name: program.organization_name,
      role: "other" as const,
      position: 0,
    },
  ];
}
