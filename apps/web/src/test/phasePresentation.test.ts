import { expect, it } from "vitest";

import { compactPhaseLabels, developmentPhases, phaseDisplayOrder, phaseLabel } from "../lib/phasePresentation";

it("keeps early clinical and unknown stages visible and distinct from preclinical", () => {
  expect(phaseLabel("early_phase_1")).toBe("早期 I 期临床");
  expect(phaseLabel("unknown")).toBe("阶段未知");
  expect(phaseLabel(null)).toBe("未披露");
  expect(compactPhaseLabels.early_phase_1).toBe("早期 I 期");
  expect(developmentPhases.has("early_phase_1")).toBe(true);
  expect(developmentPhases.has("unknown")).toBe(true);
  expect(phaseDisplayOrder.indexOf("early_phase_1")).toBeLessThan(phaseDisplayOrder.indexOf("preclinical"));
});
