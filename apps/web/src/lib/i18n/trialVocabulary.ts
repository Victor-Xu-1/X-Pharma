import { clinicalTrialPhaseLabel, clinicalTrialStatusLabel, clinicalTrialStudyTypeLabel } from "../trialDisplay";
import { professionalEnumLabel, professionalEnumMessages } from "./professionalEnums";
import { createTranslator } from "./translator";

/** Captions from the existing trial registry only. Raw codes and science stay unchanged. */
export const trialVocabularyMessages = {
  尚未招募: "Not yet recruiting",
  招募中: "Recruiting",
  邀请入组: "Enrolling by invitation",
  "进行中，停止招募": "Active, not recruiting",
  暂停: "Suspended",
  终止: "Terminated",
  已完成: "Completed",
  撤回: "Withdrawn",
  未知: "Unknown",
  不适用: "Not applicable",
  干预性研究: "Interventional study",
  观察性研究: "Observational study",
  扩大使用: "Expanded access",
} as const;
const text = createTranslator(trialVocabularyMessages);
function registeredCaption(value: string, label: (value: string) => string): string {
  if (!value.trim()) return value;
  const caption = label(value);
  if (caption === value.trim().replaceAll("_", " ")) return value;
  if (Object.hasOwn(trialVocabularyMessages, caption)) return text(caption as keyof typeof trialVocabularyMessages);
  return Object.hasOwn(professionalEnumMessages, caption) ? professionalEnumLabel(caption, value) : value;
}
export const localizedTrialPhase = (value: string) => registeredCaption(value, clinicalTrialPhaseLabel);
export const localizedTrialStatus = (value: string) => registeredCaption(value, clinicalTrialStatusLabel);
export const localizedTrialStudyType = (value: string) => registeredCaption(value, clinicalTrialStudyTypeLabel);
