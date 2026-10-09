import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { newsEventTypeLabels } from "../../lib/newsDisplay";

/** Only the existing project-owned controlled vocabulary is translated. */
export function newsTypeLabel(code: string): string {
  return Object.hasOwn(newsEventTypeLabels, code) ? professionalEnumLabel(newsEventTypeLabels[code], code) : code;
}
