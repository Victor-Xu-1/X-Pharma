import type { ProfessionalSearchDraft } from "../../../lib/professionalSearch";

/** Derived governed options only; no state or request authority. */
export function trialsOptions(draft: ProfessionalSearchDraft) {
  const trialProfileConditionCount = [
    draft.trialAcronym,
    draft.trialInitiationType,
    draft.trialTherapyLine,
    draft.trialResultEvaluation,
  ].filter(Boolean).length;
  const trialEvidenceConditionCount = [
    draft.trialHasKeyResult,
    draft.trialPublicationId,
    draft.trialConference,
    draft.trialDisclosedFrom,
    draft.trialDisclosedTo,
  ].filter(Boolean).length;

  return { trialProfileConditionCount, trialEvidenceConditionCount };
}
