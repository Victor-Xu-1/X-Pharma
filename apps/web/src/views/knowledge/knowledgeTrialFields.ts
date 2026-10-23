import { formattingLocale } from "../../lib/i18n";
import { knowledgeFieldText } from "../../lib/i18n/knowledgeFields";
import { localizedTrialPhase, localizedTrialStatus, localizedTrialStudyType } from "../../lib/i18n/trialVocabulary";
import { recordedCalendarDate } from "../../lib/recordedCalendarDate";

const precisionLabels = { day: "日", month: "月", year: "年" } as const;
const enrollmentLabels = { ACTUAL: "实际人数", ESTIMATED: "预计人数" } as const;

/** Null delegates unknown shapes/values to the complete literal reader. */
export function knowledgeTrialFieldText(value: unknown, key: string, record: Record<string, unknown>): string | null {
  if (key === "phases" && Array.isArray(value) && value.length && value.every((phase) => typeof phase === "string")) {
    return value.map(localizedTrialPhase).join(formattingLocale() === "en-US" ? ", " : "、");
  }
  if (typeof value !== "string") return null;
  if (key === "overall_status") return localizedTrialStatus(value);
  if (key === "study_type") return localizedTrialStudyType(value);
  if (key === "enrollment_type")
    return Object.hasOwn(enrollmentLabels, value)
      ? knowledgeFieldText(enrollmentLabels[value as keyof typeof enrollmentLabels])
      : value;
  if (key === "start_date_precision" || key === "completion_date_precision") {
    return Object.hasOwn(precisionLabels, value)
      ? knowledgeFieldText(precisionLabels[value as keyof typeof precisionLabels])
      : value;
  }
  if (key === "start_date") return recordedCalendarDate(value, record.start_date_precision);
  if (key === "completion_date") return recordedCalendarDate(value, record.completion_date_precision);
  if (key === "results_first_posted" || key === "last_update_posted") return recordedCalendarDate(value, "day");
  return null;
}
