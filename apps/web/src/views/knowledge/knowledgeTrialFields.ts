import { formattingLocale, getLocale } from "../../lib/i18n";
import { knowledgeFieldMessages, knowledgeFieldText } from "../../lib/i18n/knowledgeFields";
import { professionalEnumLabel, professionalEnumMessages } from "../../lib/i18n/professionalEnums";
import { clinicalTrialPhaseLabel, clinicalTrialStatusLabel, clinicalTrialStudyTypeLabel } from "../../lib/trialDisplay";

const precisionLabels = { day: "日", month: "月", year: "年" } as const;
const enrollmentLabels = { ACTUAL: "实际人数", ESTIMATED: "预计人数" } as const;

function knownVocabulary(value: string, label: (value: string) => string): string {
  if (!value.trim()) return value;
  const readable = label(value);
  if (readable === value.trim().replaceAll("_", " ")) return value;
  if (Object.hasOwn(knowledgeFieldMessages, readable))
    return knowledgeFieldText(readable as keyof typeof knowledgeFieldMessages);
  if (Object.hasOwn(professionalEnumMessages, readable)) return professionalEnumLabel(readable);
  return readable;
}

/** Only a recorded calendar date and its declared precision are formatted; no local-time conversion. */
function recordedDate(value: string, precision: unknown): string | null {
  if (typeof precision !== "string" || !Object.hasOwn(precisionLabels, precision)) return null;
  const match = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?(?:T00:00:00(?:\.0+)?(?:Z|\+00:00))?$/.exec(value);
  if (!match) return null;
  const [, year, month, day] = match;
  if (value.includes("T") && !day) return null;
  if (day) {
    const calendar = `${year}-${month}-${day}`;
    const parsed = new Date(`${calendar}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== calendar) return null;
  } else if (month && (Number(month) < 1 || Number(month) > 12)) return null;
  if (precision === "year") return getLocale() === "en" ? year : `${year}年`;
  if (!month) return null;
  if (precision === "month") return getLocale() === "en" ? `${year}-${month}` : `${year}年${month}月`;
  return day ? (getLocale() === "en" ? `${year}-${month}-${day}` : `${year}年${month}月${day}日`) : null;
}

/** Null delegates unknown shapes/values to the complete literal reader. */
export function knowledgeTrialFieldText(value: unknown, key: string, record: Record<string, unknown>): string | null {
  if (key === "phases" && Array.isArray(value) && value.length && value.every((phase) => typeof phase === "string")) {
    return value
      .map((phase) => knownVocabulary(phase, clinicalTrialPhaseLabel))
      .join(formattingLocale() === "en-US" ? ", " : "、");
  }
  if (typeof value !== "string") return null;
  if (key === "overall_status") return knownVocabulary(value, clinicalTrialStatusLabel);
  if (key === "study_type") return knownVocabulary(value, clinicalTrialStudyTypeLabel);
  if (key === "enrollment_type")
    return Object.hasOwn(enrollmentLabels, value)
      ? knowledgeFieldText(enrollmentLabels[value as keyof typeof enrollmentLabels])
      : value;
  if (key === "start_date_precision" || key === "completion_date_precision") {
    return Object.hasOwn(precisionLabels, value)
      ? knowledgeFieldText(precisionLabels[value as keyof typeof precisionLabels])
      : value;
  }
  if (key === "start_date") return recordedDate(value, record.start_date_precision);
  if (key === "completion_date") return recordedDate(value, record.completion_date_precision);
  if (key === "results_first_posted" || key === "last_update_posted") return recordedDate(value, "day");
  return null;
}
