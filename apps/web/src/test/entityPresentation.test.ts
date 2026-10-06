import { describe, expect, it } from "vitest";

import {
  entityIdentityNote,
  entityTypeLabel,
  isProviderLabel,
  matchExplanation,
  relationshipLabel,
} from "../lib/entityPresentation";
import type { Entity } from "../lib/types";

const identity = { entity_type: "disease", attributes: {} } as Pick<Entity, "entity_type" | "attributes">;

describe("source-scoped identity presentation", () => {
  it("does not infer a label scope from a name or provider alone", () => {
    const canonical = { ...identity, attributes: { label_provider: "ClinicalTrials.gov" } };
    expect(isProviderLabel(canonical)).toBe(false);
    expect(entityTypeLabel(canonical)).toBe("疾病");
    expect(entityIdentityNote(canonical)).toBeNull();
  });

  it.each([
    ["disease", "登记条件"],
    ["organization", "登记申办方"],
  ] as const)("labels a typed provider identity without renaming its source: %s", (entity_type, label) => {
    const scoped = { ...identity, entity_type, attributes: { identity_scope: "provider_label" } };
    expect(entityTypeLabel(scoped)).toBe(label);
    expect(entityIdentityNote(scoped)).toContain("不代表");
  });

  it("preserves the explicit safe identity note", () => {
    expect(
      entityIdentityNote({
        ...identity,
        attributes: { identity_scope: "provider_label", identity_note: "原始来源名称范围" },
      }),
    ).toBe("原始来源名称范围");
  });

  it("localizes known relationship explanations without inventing unknown relationships", () => {
    const entity = {
      ...identity,
      match: { match_type: "relationship", matched_value: "EGFR", predicate: "has_target" },
    } as unknown as Entity;
    expect(matchExplanation(entity)).toBe("关联命中：EGFR · 作用靶点");
    expect(relationshipLabel("has_competitor")).toBe("竞品关系");
    expect(relationshipLabel("custom_predicate")).toBe("custom_predicate");
  });
});
