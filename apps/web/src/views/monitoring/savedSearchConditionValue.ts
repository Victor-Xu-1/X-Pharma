import {
  dealTypeLabels,
  directionLabels,
  partyRoleLabels,
  phaseLabels,
  rightTypeLabels,
  statusLabels,
} from "../../lib/dealDisplay";
import { formattingLocale } from "../../lib/i18n";
import { professionalEnumLabel, professionalEnumMessages } from "../../lib/i18n/professionalEnums";
import { localizedProgramModality } from "../../lib/i18n/programVocabulary";
import { savedSearchText as text } from "../../lib/i18n/savedSearch";
import { localizedTrialPhase, localizedTrialStatus, localizedTrialStudyType } from "../../lib/i18n/trialVocabulary";
import type { SavedSearchConditionKind } from "./savedSearchConditionFields";

/** Read-only captions use existing vocabularies; unrecognized scalar codes stay literal. */
function scalarCaption(value: string, key: string, queryType: string): string {
  if (key.includes("modality")) return localizedProgramModality(value);
  if (key.includes("phase") && Object.hasOwn(phaseLabels, value))
    return professionalEnumLabel(phaseLabels[value], value);
  if (queryType === "clinical_trial_search") {
    if (key === "phase") return localizedTrialPhase(value);
    if (key === "status") return localizedTrialStatus(value);
    if (key === "study_type") return localizedTrialStudyType(value);
  }
  const dealRegistry: Record<string, Record<string, string>> = {
    deal_type: dealTypeLabels,
    status: statusLabels,
    direction: directionLabels,
    party_role: partyRoleLabels,
    right_type: rightTypeLabels,
  };
  if (queryType === "deal_search" && Object.hasOwn(dealRegistry, key)) {
    const labels = dealRegistry[key];
    if (Object.hasOwn(labels, value) && Object.hasOwn(professionalEnumMessages, labels[value]))
      return professionalEnumLabel(labels[value], value);
  }
  return value;
}

export function savedSearchConditionValue(
  value: unknown,
  key: string,
  queryType: string,
  kind: SavedSearchConditionKind = "enum",
): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (Array.isArray(value)) {
    if (!value.length) return null;
    if (kind === "entity")
      return value.length === 1
        ? text("已选")
        : text("已选{count}项", { count: new Intl.NumberFormat(formattingLocale()).format(value.length) });
    return value
      .map((item) => (typeof item === "string" ? scalarCaption(item, key, queryType) : String(item)))
      .join(formattingLocale() === "en-US" ? ", " : "、");
  }
  if (kind === "entity") return text("已选");
  if (kind === "boolean") return typeof value === "boolean" ? (value ? text("是") : text("否")) : text("已设置");
  if (kind === "text" || kind === "date") return String(value);
  if (typeof value === "string") return scalarCaption(value, key, queryType);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return text("已设置");
}
