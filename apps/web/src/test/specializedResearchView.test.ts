import { expect, it } from "vitest";
import type { Entity } from "../lib/types";
import { researchRouteEntity, specializedResearchView } from "../workspaces/research/locationModel";

const current: Entity = {
  id: "current-id",
  entity_type: "patent",
  name: "原始 Source identity",
  description: null,
  review_status: "verified",
  external_ids: {},
  attributes: {},
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
};
it("uses the current selected identity without requiring another metadata snapshot", () => {
  expect(researchRouteEntity(current.id, current, undefined)).toBe(current);
  expect(researchRouteEntity(current.id, current, { ...current, name: "Other loaded display" })).toBe(current);
});
it("does not bind foreign or absent identities to the current route", () => {
  const foreign = { ...current, id: "foreign-id" };
  expect(researchRouteEntity(current.id, foreign, current)).toBe(current);
  expect(researchRouteEntity(current.id, null, foreign)).toBeNull();
  expect(researchRouteEntity(undefined, current, current)).toBeNull();
});

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
