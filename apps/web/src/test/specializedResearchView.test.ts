import { expect, it } from "vitest";
import { specializedResearchView } from "../workspaces/research/locationModel";

it.each([
  ["target", "target"],
  ["drug", "drug"],
  ["organization", "company"],
  ["disease", "disease"],
] as const)("routes recorded %s identities to the existing %s dossier", (source, view) => {
  expect(specializedResearchView(source)).toBe(view);
});

it.each(["patent", "clinical_trial", "transaction", "SOURCE_FUTURE_TYPE", "__proto__", "constructor", "", undefined])(
  "retains the generic route for source type %s without guessing a specialization",
  (source) => {
    expect(specializedResearchView(source)).toBeNull();
  },
);
