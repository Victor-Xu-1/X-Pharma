import { useLocale } from "../../lib/i18n";
import { clinicalCaption } from "../../lib/i18n/clinical";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { localizedTrialPhase, localizedTrialStatus, localizedTrialStudyType } from "../../lib/i18n/trialVocabulary";
import { trialLinkedPhaseLabels } from "../../lib/phasePresentation";
import { trialInitiationTypeLabels, trialResultEvaluationLabels, trialTherapyLineLabels } from "../../lib/trialFilters";
import type { TrialFilterConditions } from "./useTrialFilterDraft";
import { appliedFilterLabels, trialRoleLabels } from "./vocabulary";

const translateDictionary = (
  labels: Readonly<Record<string, string>>,
  translate: (label: string, code: string) => string,
) => Object.fromEntries(Object.entries(labels).map(([code, label]) => [code, translate(label, code)]));

export function useTrialAppliedLabels(input: TrialFilterConditions, entities: Readonly<Record<string, string>>) {
  useLocale();
  return {
    labels: translateDictionary(appliedFilterLabels, clinicalCaption),
    valueLabels: {
      phase: { [input.phase]: localizedTrialPhase(input.phase) },
      status: { [input.status]: localizedTrialStatus(input.status) },
      study_type: { [input.studyType]: localizedTrialStudyType(input.studyType) },
      result_evaluation: translateDictionary(trialResultEvaluationLabels, professionalEnumLabel),
      initiation_type: translateDictionary(trialInitiationTypeLabels, professionalEnumLabel),
      therapy_line: translateDictionary(trialTherapyLineLabels, professionalEnumLabel),
      linked_drug_global_phase: translateDictionary(trialLinkedPhaseLabels, professionalEnumLabel),
      role_entity_role: translateDictionary(trialRoleLabels, clinicalCaption),
      ...Object.fromEntries(
        [
          "role_entity_id",
          "role_entity_ids",
          "investigational_drug_entity_ids",
          "combination_drug_entity_ids",
          "investigational_target_entity_ids",
          "combination_target_entity_ids",
        ].map((field) => [field, entities]),
      ),
    },
  };
}
