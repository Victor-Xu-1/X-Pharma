import { act, render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import { EntityIdentityNotice } from "../components/EntityIdentityNotice";
import { entityIdentityNote } from "../lib/entityPresentation";
import { setLocale } from "../lib/i18n";
import type { Entity } from "../lib/types";

const notices = [
  {
    entity_type: "organization",
    note: "ClinicalTrials.gov申办方名称，不代表已核实的法律主体或企业集团归并。",
    english:
      "ClinicalTrials.gov sponsor label; it does not establish a verified legal entity or corporate-group identity.",
  },
  {
    entity_type: "disease",
    note: "ClinicalTrials.gov研究条件名称，不代表获批适应症或本体标准化。",
    english:
      "ClinicalTrials.gov study condition label; it does not establish an approved indication or a standardized ontology term.",
  },
] as const;
beforeEach(() => setLocale("en"));

it.each(notices)(
  "localizes the exact application-owned $entity_type caveat without changing its stored attributes",
  ({ entity_type, note, english }) => {
    const entity = {
      entity_type,
      attributes: { identity_scope: "provider_label", label_provider: "ClinicalTrials.gov", identity_note: note },
    };
    const original = JSON.stringify(entity);
    render(<EntityIdentityNotice entity={entity} />);
    expect(screen.getByRole("note", { name: "Source name scope" })).toHaveTextContent(english);
    act(() => setLocale("zh-CN"));
    expect(screen.getByRole("note", { name: "来源名称范围" })).toHaveTextContent(note);
    expect(JSON.stringify(entity)).toBe(original);
  },
);

const organization: Pick<Entity, "entity_type" | "attributes"> = {
  entity_type: "organization",
  attributes: {
    identity_scope: "provider_label",
    label_provider: "ClinicalTrials.gov",
    identity_note: notices[0].note,
  },
};
it.each([
  { ...organization, attributes: { ...organization.attributes, label_provider: "OTHER_PROVIDER" } },
  { ...organization, attributes: { identity_scope: "provider_label", identity_note: notices[0].note } },
  { ...organization, attributes: { ...organization.attributes, identity_note: notices[1].note } },
  { ...organization, attributes: { ...organization.attributes, identity_note: ` ${notices[0].note}` } },
  { ...organization, attributes: { ...organization.attributes, identity_note: "原始范围 <source> 0.00000012345" } },
])("preserves unrecognized provider/type/copy and source-owned notes verbatim: %j", (entity) => {
  for (const locale of ["en", "zh-CN"] as const) {
    setLocale(locale);
    expect(entityIdentityNote(entity)).toBe(entity.attributes.identity_note);
  }
});

it.each(["canonical", "unverified", undefined])(
  "does not infer a provider-label scope from application copy: %s",
  (identity_scope) => {
    expect(
      entityIdentityNote({ ...organization, attributes: { ...organization.attributes, identity_scope } }),
    ).toBeNull();
  },
);
