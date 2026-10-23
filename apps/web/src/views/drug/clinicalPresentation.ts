import { drugDossierText as t } from "../../lib/i18n/drugDossier";
export function clinicalList(values: string[], empty = t("未披露"), max = 2) {
  if (!values.length) return empty;
  const visible = values.slice(0, max).join(t("、"));
  return values.length > max ? t("{values} 等 {count} 项", { values: visible, count: values.length }) : visible;
}

export function clinicalObjectNames(values: Array<{ name: string }>, empty = t("未披露"), max = 2) {
  return clinicalList(values.map((item) => item.name).filter(Boolean), empty, max);
}
