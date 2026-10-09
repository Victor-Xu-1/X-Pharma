import { clinicalCaption, clinicalMessages } from "./clinical";
import { drugDossierCaption, drugDossierMessages } from "./drugDossier";
import { professionalEnumLabel, professionalEnumMessages } from "./professionalEnums";

/** Controlled captions shared by dossier families; unknown source codes remain literal. */
export function controlledDossierLabel(
  value: string | null | undefined,
  labels: Readonly<Record<string, string>>,
): string {
  if (value == null || value === "") return drugDossierCaption("未披露");
  const caption = labels[value];
  if (!caption) return value;
  if (Object.hasOwn(professionalEnumMessages, caption)) return professionalEnumLabel(caption, value);
  if (Object.hasOwn(drugDossierMessages, caption)) return drugDossierCaption(caption);
  if (Object.hasOwn(clinicalMessages, caption)) return clinicalCaption(caption);
  return caption;
}
