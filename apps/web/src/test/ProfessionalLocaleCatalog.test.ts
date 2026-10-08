import { expect, it } from "vitest";
import {
  domains,
  pipelineOrganizationRoleLabels,
  pipelinePhases,
  pipelineProgramStatusLabels,
  trialPhases,
} from "../components/professionalQuery/presentation";
import { patentLegalStatusLabels } from "../lib/contracts/patents";
import {
  dealTypeLabels,
  directionLabels,
  partyRoleLabels,
  phaseLabels,
  rightTypeLabels,
  statusLabels,
} from "../lib/dealDisplay";
import { epidemiologyMeasureLabels, epidemiologySexLabels } from "../lib/epidemiologyDisplay";
import { setLocale } from "../lib/i18n";
import { professionalEnumLabel, professionalEnumMessages } from "../lib/i18n/professionalEnums";
import { professionalQueryLabel, professionalQueryMessages } from "../lib/i18n/professionalQuery";
import { professionalValidationMessages, professionalValidationText } from "../lib/i18n/professionalValidation";
import { newsEventTypeLabels, newsLanguageLabels } from "../lib/newsDisplay";
import { pipelineBooleanSignalLabels, pipelineResultEvaluationLabels } from "../lib/pipelineSignals";
import { createProfessionalSearchDraft, validateProfessionalSearch } from "../lib/professionalSearch";
import {
  boxedWarningLabels,
  designationLabels,
  eventTypeLabels,
  labelChangeLabels,
  safetySignalLabels,
  safetyStatusLabels,
  severityLabels,
} from "../lib/regulatoryDisplay";
import {
  trialInitiationTypeLabels,
  trialKeyResultLabels,
  trialResultEvaluationLabels,
  trialTherapyLineLabels,
} from "../lib/trialFilters";

it("covers every project-owned professional enum caption, leaving stable codes unchanged", () => {
  const dictionaries = [
    patentLegalStatusLabels,
    dealTypeLabels,
    directionLabels,
    partyRoleLabels,
    phaseLabels,
    rightTypeLabels,
    statusLabels,
    epidemiologyMeasureLabels,
    epidemiologySexLabels,
    newsEventTypeLabels,
    newsLanguageLabels,
    pipelineBooleanSignalLabels,
    pipelineResultEvaluationLabels,
    boxedWarningLabels,
    designationLabels,
    eventTypeLabels,
    labelChangeLabels,
    safetySignalLabels,
    safetyStatusLabels,
    severityLabels,
    trialInitiationTypeLabels,
    trialKeyResultLabels,
    trialResultEvaluationLabels,
    trialTherapyLineLabels,
    pipelineOrganizationRoleLabels,
    pipelineProgramStatusLabels,
    Object.fromEntries(pipelinePhases),
    Object.fromEntries(trialPhases),
  ];
  for (const dictionary of dictionaries)
    for (const [code, label] of Object.entries(dictionary)) {
      setLocale("zh-CN");
      expect(professionalEnumLabel(label, code)).toBe(label);
      setLocale("en");
      expect(professionalEnumLabel(label, code)).not.toMatch(/[\u3400-\u9fff]/u);
    }
  expect(professionalEnumLabel("申报", "filed")).toBe("Filed");
  expect(professionalEnumLabel("申报", "submission")).toBe("Submission");
  expect(professionalEnumLabel("合作方", "partner")).toBe("Partner");
  expect(professionalEnumLabel("合作方", "collaborator")).toBe("Collaborator");
});

it("covers all domain headings and preserves interpolation parameters", () => {
  setLocale("en");
  for (const domain of domains)
    for (const label of [domain.label, domain.detail])
      expect(professionalQueryLabel(label)).not.toMatch(/[\u3400-\u9fff]/u);
  const parameters = (value: string) =>
    [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const catalog of [professionalQueryMessages, professionalEnumMessages, professionalValidationMessages])
    for (const [key, english] of Object.entries(catalog)) {
      expect(english.trim(), key).not.toBe("");
      expect(parameters(key), key).toEqual(parameters(english));
    }
});

it("uses current-language validation presentation while preserving the canonical validation contract", () => {
  const draft = {
    ...createProfessionalSearchDraft("pipeline", "EGFR"),
    statusDateFrom: "2026-10-08",
    statusDateTo: "2026-10-01",
  };
  const original = validateProfessionalSearch(draft);
  expect(original).toBe("状态日期起始值不能晚于结束值");
  setLocale("en");
  expect(professionalValidationText(original ?? "")).toBe("Status date: the start must not be later than the end");
  expect(validateProfessionalSearch(draft)).toBe(original);
  expect(professionalValidationText("未登记的诊断原文")).toBe("未登记的诊断原文");
  setLocale("zh-CN");
  expect(professionalValidationText(original ?? "")).toBe(original);
});
